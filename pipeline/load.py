"""Load the five supplied workbooks into ``build/attractions.duckdb``.

Run with ``python -m pipeline.load``. The database is built in a temporary
file and swapped in, so a failed load leaves the previous one in place. Guest
personal data and free-text columns are read for in-load checks only and are
never written to the database (D-009).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from pipeline import rules

SOURCES = {
    "ticketing": ("01_Ticketing.xlsx", ["fact_ticket", "dim_package", "dim_merchant"]),
    "pos": ("02_POS_FandB_Merch.xlsx", ["pos_order_lines"]),
    "events": ("03_Private_Events.xlsx", ["private_events"]),
    "labor": ("04_Labor.xlsx", ["labor_actual"]),
    "reference": ("05_Reference_Budget_Context.xlsx", ["dim_venue", "budget_daily"]),
}
BUDGET_DEPARTMENTS = {"Ticket", "Restaurant", "Cafe", "Merchandise", "Private Events"}
# Development sign-ins. In Azure, Entra ID supplies the user and this table
# supplies the venues they may see.
DEV_USERS = [
    ("nick@dev", "Nick Melamed", "admin", ["SSD", "RTL", "TRO"]),
    ("marcus@dev", "Marcus", "venue_manager", ["SSD"]),
]
ROLLUPS = [
    "dim_venue",
    "dim_package",
    "daily_tickets",
    "daily_pos",
    "daily_labor",
    "daily_private_events",
    "budget_daily",
    "feed_coverage",
]


MISSING_RATE_COLS = ["missing_rate_shifts", "missing_rate_hours"]


class LoadError(RuntimeError):
    """The load cannot produce a trustworthy database."""


@dataclass
class Checks:
    """Data quality results for one run."""

    rows: list[dict] = field(default_factory=list)

    def add(self, check: str, severity: str, failed: int, detail: str) -> None:
        """Record a check. ``failed`` counts rows or orders that did not pass."""
        self.rows.append(
            {
                "check_name": check,
                "severity": severity,
                "status": "noted"
                if severity == "info"
                else ("pass" if failed == 0 else "fail"),
                "rows_affected": int(failed),
                "detail": detail,
            }
        )

    def blocking_failures(self) -> list[dict]:
        """Return failed checks that must stop the load."""
        return [
            r
            for r in self.rows
            if r["severity"] == "blocking" and r["status"] == "fail"
        ]


def read_sources(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Read every needed sheet, or raise naming the missing files."""
    missing = [name for name, _ in SOURCES.values() if not (data_dir / name).exists()]
    if missing:
        raise LoadError(
            f"missing input files in {data_dir}/: {', '.join(missing)}. "
            "Copy the supplied workbooks into data/ (see README)."
        )
    frames = {}
    for filename, sheets in SOURCES.values():
        for sheet in sheets:
            frames[sheet] = pd.read_excel(
                data_dir / filename, sheet_name=sheet, engine="calamine"
            )
    return frames


def _ticket_tables(src, venues, checks):
    raw = src["fact_ticket"].copy()
    raw["ingestion_ts"] = pd.to_datetime(raw["ingestion_ts"])
    checks.add(
        "ticket_duplicate_loads_agree",
        "blocking",
        rules.conflicting_duplicate_loads(raw),
        "ticket_line_id copies that differ in more than ingestion_ts",
    )
    tickets, dropped = rules.dedup_ticket_loads(raw)
    checks.add(
        "ticket_duplicate_loads_dropped",
        "info",
        dropped,
        "ticket_line_id loaded more than once, latest ingestion_ts kept",
    )
    packages = src["dim_package"][
        ["package_id", "package_class", "internal_name", "ticket_type"]
    ]
    merchants = src["dim_merchant"][["merchant_id", "sales_channel"]]
    tickets = tickets.merge(packages, on="package_id", how="left", validate="m:1")
    tickets = tickets.merge(merchants, on="merchant_id", how="left", validate="m:1")
    unjoined = tickets["package_class"].isna() | tickets["sales_channel"].isna()
    checks.add(
        "ticket_dimension_join",
        "blocking",
        unjoined.sum(),
        "ticket lines whose package_id or merchant_id is not in the dimensions",
    )
    if unjoined.any():
        return None, None
    tickets["is_countable"] = rules.countable_ticket_mask(tickets)
    tz = venues.set_index("venue_code")["timezone"]
    checks.add(
        "ticket_event_time_matches_event_date",
        "warn",
        sum(
            rules.ticket_event_time_mismatches(rows, tz[venue])
            for venue, rows in tickets.groupby("attraction_prefix")
        ),
        "lines whose event_time, converted to local, is not on event_date",
    )
    fact = pd.DataFrame(
        {
            "ticket_line_id": tickets["ticket_line_id"],
            "venue_code": tickets["attraction_prefix"],
            "source_system": tickets["source_system"],
            "event_date": rules.ticket_business_dates(tickets),
            "date_sold": pd.to_datetime(tickets["date_sold"]).dt.date,
            "package_id": tickets["package_id"],
            "package_class": tickets["package_class"],
            "internal_name": tickets["internal_name"],
            "sales_channel": tickets["sales_channel"],
            "ticket_status": tickets["ticket_status"],
            "quantity": tickets["quantity"].astype("int64"),
            "ticket_value_cents": rules.to_cents(tickets["ticket_value"]),
            "is_countable": tickets["is_countable"],
        }
    )
    daily = (
        fact[fact["is_countable"]]
        .groupby(
            ["venue_code", "event_date", "package_class", "sales_channel"],
            as_index=False,
        )
        .agg(
            attendance=("quantity", "sum"),
            ticket_revenue_cents=("ticket_value_cents", "sum"),
            lines=("ticket_line_id", "count"),
        )
        .rename(columns={"event_date": "business_date"})
    )
    return fact, daily


def _pos_tables(src, venues, checks):
    pos = src["pos_order_lines"].copy()
    for outlet in pos["outlet"].unique():
        rules.outlet_department(outlet)
    mismatched = rules.order_subtotal_mismatches(pos)
    checks.add(
        "pos_order_subtotal_matches_lines",
        "blocking",
        mismatched,
        "orders whose subtotal differs from the sum of non-void net lines",
    )
    checks.add(
        "pos_voided_lines",
        "info",
        (pos["is_voided"] == "Y").sum(),
        "voided lines, excluded from revenue",
    )
    tz = venues.set_index("venue_code")["timezone"]
    stamps = pd.to_datetime(pos["order_created_date"])
    local = pd.concat(
        rules.to_local(stamps[pos["venue_code"] == v], tz[v], rules.POS_TIMESTAMP_ZONE)
        for v in pos["venue_code"].unique()
    ).sort_index()
    fact = pd.DataFrame(
        {
            "venue_code": pos["venue_code"],
            "outlet": pos["outlet"],
            "department": pos["outlet"].map(rules.outlet_department),
            "revenue_line": pos["outlet"].map(rules.outlet_revenue_line),
            "business_date": rules.business_dates(local),
            "product_category": pos["product_category"],
            "item_quantity": pos["item_quantity"].astype("int64"),
            "is_voided": pos["is_voided"] == "Y",
            "revenue_cents": rules.pos_line_revenue_cents(pos),
        }
    )
    sold = fact.groupby(["venue_code", "business_date", "outlet"], as_index=False).agg(
        revenue_cents=("revenue_cents", "sum"), lines=("outlet", "size")
    )
    # Every outlet on every day its venue traded, so a quiet Bar shows $0.
    venue_days = fact[["venue_code", "business_date"]].drop_duplicates()
    outlets = fact[["venue_code", "outlet"]].drop_duplicates()
    grid = venue_days.merge(outlets, on="venue_code").merge(
        sold, on=["venue_code", "business_date", "outlet"], how="left"
    )
    grid["revenue_cents"] = [
        rules.outlet_day_value(pd.notna(lines), True, cents)
        for lines, cents in zip(grid["lines"], grid["revenue_cents"], strict=True)
    ]
    grid["revenue_cents"] = grid["revenue_cents"].astype("int64")
    grid["lines"] = grid["lines"].fillna(0).astype("int64")
    grid["department"] = grid["outlet"].map(rules.outlet_department)
    grid["revenue_line"] = grid["outlet"].map(rules.outlet_revenue_line)
    return fact, grid


def _labor_tables(src, venues, checks):
    labor = src["labor_actual"].copy()
    for col in ("date", "actual_in", "actual_out"):
        labor[col] = pd.to_datetime(labor[col])
    names = venues["venue_name"].tolist()
    location = labor["location_name"].map(lambda v: rules.normalise_location(v, names))
    expected = labor["venue_code"].map(venues.set_index("venue_code")["venue_name"])
    checks.add(
        "labor_location_matches_venue",
        "blocking",
        (location != expected).sum(),
        "shifts whose location_name names another venue",
    )
    measures = rules.labor_shift_measures(labor)
    checks.add(
        "labor_missing_rate",
        "warn",
        measures["missing_rate"].sum(),
        "shifts with hours but no rate or earnings, payroll marked incomplete",
    )
    ordered = labor.sort_values(["person_id", "actual_in"])
    overlaps = ordered["actual_in"] < ordered.groupby("person_id")["actual_out"].shift()
    checks.add(
        "labor_overlapping_shifts",
        "info",
        overlaps.sum(),
        "shifts starting before the same person's previous shift ended, counted",
    )
    key = ["venue_code", "person_id", "date", "actual_in"]
    checks.add(
        "labor_business_key_duplicates",
        "info",
        labor.duplicated(key).sum(),
        "shifts sharing venue, person, date and clock-in",
    )
    fact = pd.DataFrame(
        {
            "venue_code": labor["venue_code"],
            "work_date": measures["work_date"],
            "department": labor["working_dept"].map(rules.labor_department),
            "position": labor["position"],
            "hours": measures["hours"],
            "payroll_cents": measures["payroll_cents"],
            "missing_rate": measures["missing_rate"],
            "overnight": labor["actual_out"].dt.date > labor["actual_in"].dt.date,
        }
    )
    fact["missing_rate_hours"] = fact["hours"].where(fact["missing_rate"], 0.0)
    keys = ["venue_code", "work_date", "department"]
    daily = fact.groupby(keys, as_index=False).agg(
        hours=("hours", "sum"),
        shifts=("hours", "size"),
        missing_rate_shifts=("missing_rate", "sum"),
        missing_rate_hours=("missing_rate_hours", "sum"),
    )
    # A department-day where no shift has a rate has unknown payroll, not $0.
    payroll = fact.groupby(keys)["payroll_cents"].sum(min_count=1)
    daily["payroll_cents"] = payroll.to_numpy()
    daily["payroll_cents"] = daily["payroll_cents"].astype("Int64")
    daily = daily[keys + ["hours", "payroll_cents", "shifts"] + MISSING_RATE_COLS]
    return fact.drop(columns="missing_rate_hours"), daily


def _event_tables(src):
    events = src["private_events"].copy()
    events["event_date"] = pd.to_datetime(events["event_date"])
    revenue = rules.private_event_revenue(events)
    revenue["venue_code"] = events.loc[revenue.index, "venue_code"]
    revenue["event_id"] = events.loc[revenue.index, "event_id"]
    revenue["market_segment"] = events.loc[revenue.index, "booking_market_segment"]
    daily = revenue.groupby(["venue_code", "event_date"], as_index=False).agg(
        revenue_cents=("revenue_cents", "sum"),
        events=("event_id", "count"),
        bookings=("booking_id", "nunique"),
    )
    return revenue, daily


def _coverage(feeds, today):
    """Return one row per venue, feed and day with ok or no_data."""
    rows = []
    for feed, (frame, date_col) in feeds.items():
        last = min(frame[date_col].max(), today - timedelta(days=1))
        first = frame[date_col].min()
        for venue, days in frame.groupby("venue_code")[date_col]:
            status = rules.feed_day_status(set(days), first, last)
            rows += [(venue, d, feed, s) for d, s in status.items()]
    return pd.DataFrame(
        rows, columns=["venue_code", "business_date", "feed", "status"]
    ).sort_values(["venue_code", "feed", "business_date"], ignore_index=True)


def transform(src: dict[str, pd.DataFrame], today: date) -> tuple[dict, Checks]:
    """Apply the rules and return the output tables and the check results."""
    checks = Checks()
    venues = src["dim_venue"][
        ["venue_code", "venue_name", "city", "state", "timezone", "location_id"]
    ].copy()
    ticket_fact, daily_tickets = _ticket_tables(src, venues, checks)
    if ticket_fact is None:
        return {}, checks
    pos_fact, daily_pos = _pos_tables(src, venues, checks)
    labor_fact, daily_labor = _labor_tables(src, venues, checks)
    event_fact, daily_events = _event_tables(src)

    budget = src["budget_daily"].copy()
    budget["date"] = pd.to_datetime(budget["date"]).dt.date
    unknown = set(budget["department"]) - BUDGET_DEPARTMENTS
    if unknown:
        raise rules.UnmappedLabel(f"budget department {sorted(unknown)!r} not mapped")
    budget["budget_revenue_cents"] = rules.to_cents(budget["budget_revenue"])
    budget = budget.drop(columns="budget_revenue")

    coverage = _coverage(
        {
            "tickets": (ticket_fact, "event_date"),
            "pos": (pos_fact, "business_date"),
            "labor": (labor_fact, "work_date"),
        },
        today,
    )
    gaps = coverage[coverage["status"] == rules.FEED_NO_DATA]
    checks.add(
        "venue_day_missing_from_feed",
        "warn",
        len(gaps),
        "venue-days with no rows from a feed, shown as no data",
    )
    packages = src["dim_package"][
        [
            "package_id",
            "attraction_prefix",
            "source_system",
            "package_name",
            "package_class",
            "internal_name",
            "ticket_type",
        ]
    ].rename(columns={"attraction_prefix": "venue_code"})
    users = pd.DataFrame(
        [(e, n, r) for e, n, r, _ in DEV_USERS],
        columns=["email", "display_name", "role"],
    )
    user_venues = pd.DataFrame(
        [(e, v) for e, _, _, vs in DEV_USERS for v in vs],
        columns=["email", "venue_code"],
    )
    tables = {
        "dim_venue": venues,
        "dim_package": packages,
        "app_users": users,
        "user_venues": user_venues,
        "fact_ticket_line": ticket_fact,
        "fact_pos_line": pos_fact,
        "fact_labor_shift": labor_fact,
        "fact_private_event": event_fact,
        "budget_daily": budget,
        "daily_tickets": daily_tickets,
        "daily_pos": daily_pos,
        "daily_labor": daily_labor,
        "daily_private_events": daily_events,
        "feed_coverage": coverage,
    }
    return tables, checks


def _fingerprint(data_dir: Path) -> str:
    digest = hashlib.sha256()
    for filename, _ in SOURCES.values():
        digest.update((data_dir / filename).read_bytes())
    return digest.hexdigest()


def write(tables: dict, checks: Checks, run: dict, db_path: Path) -> None:
    """Write every table into a temp database, then swap it in."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    try:
        for name, frame in tables.items():
            con.register("frame", frame)
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM frame")
            con.unregister("frame")
        dq = pd.DataFrame(checks.rows).assign(run_id=run["run_id"])
        con.register("frame", dq)
        con.execute("CREATE TABLE data_quality AS SELECT * FROM frame")
        con.register("frame", pd.DataFrame([run]))
        con.execute("CREATE TABLE load_runs AS SELECT * FROM frame")
    finally:
        con.close()
    os.replace(tmp, db_path)


def export(db_path: Path, out_dir: Path) -> None:
    """Write each rollup as CSV sorted on every column, for byte comparison."""
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        for name in ROLLUPS:
            frame = con.execute(f"SELECT * FROM {name} ORDER BY ALL").df()
            frame.to_csv(out_dir / f"{name}.csv", index=False)
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    """Run the load and print a one-line summary per check."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.environ.get("DUCKDB_PATH", "build/attractions.duckdb")),
    )
    parser.add_argument("--export", type=Path, help="write rollup CSVs here")
    args = parser.parse_args(argv)
    today = date.fromisoformat(os.environ.get("APP_TODAY", "2026-10-05"))
    started = datetime.now().replace(microsecond=0)
    try:
        src = read_sources(args.data)
        tables, checks = transform(src, today)
    except (LoadError, rules.UnmappedLabel) as exc:
        print(f"load failed: {exc}", file=sys.stderr)
        return 1
    for row in checks.rows:
        print(
            f"{row['severity']:8} {row['status']:4} {row['rows_affected']:>6}  "
            f"{row['check_name']}"
        )
    blocking = checks.blocking_failures()
    if blocking:
        names = ", ".join(r["check_name"] for r in blocking)
        print(f"load failed: blocking checks failed: {names}", file=sys.stderr)
        return 1
    run = {
        "run_id": str(uuid.uuid4()),
        "started_at": started,
        "finished_at": datetime.now().replace(microsecond=0),
        "app_today": today,
        "source_sha256": _fingerprint(args.data),
        "max_ticket_date": min(
            tables["daily_tickets"]["business_date"].max(), today - timedelta(days=1)
        ),
        "max_pos_date": tables["daily_pos"]["business_date"].max(),
        "max_labor_date": tables["daily_labor"]["work_date"].max(),
    }
    write(tables, checks, run, args.db)
    print(f"wrote {args.db} (run {run['run_id']})")
    if args.export:
        export(args.db, args.export)
        print(f"exported rollups to {args.export}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
