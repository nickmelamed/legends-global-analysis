"""Compare the loaded week against the Power BI targets.

Run with ``python -m pipeline.reconcile`` after the load. Writes
``build/reports/reconciliation.md`` and ``reconciliation.json``, and exits
non-zero if a required venue misses. Misses are explained in
docs/RECONCILIATION.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import duckdb

TARGETS = Path("tests/fixtures/pbi_targets.json")
REPORTS = Path("build/reports")
MEASURES = [
    "attendance",
    "ticket_revenue",
    "fnb_revenue",
    "merch_revenue",
    "private_events_revenue",
    "total_revenue",
    "labor_hours",
    "payroll",
]
# Power BI shows hours to 0.1 and money and counts to the whole unit.
PRECISION = {"labor_hours": Decimal("0.1")}

WEEK_SQL = """
WITH t AS (
    SELECT sum(attendance) AS attendance, sum(ticket_revenue_cents) AS tix
    FROM daily_tickets
    WHERE venue_code = $venue AND business_date BETWEEN $start AND $end
), p AS (
    SELECT sum(revenue_cents) FILTER (WHERE revenue_line = 'fnb') AS fnb,
           sum(revenue_cents) FILTER (WHERE revenue_line = 'merch') AS merch
    FROM daily_pos
    WHERE venue_code = $venue AND business_date BETWEEN $start AND $end
), e AS (
    SELECT coalesce(sum(revenue_cents), 0) AS pe
    FROM daily_private_events
    WHERE venue_code = $venue AND event_date BETWEEN $start AND $end
), l AS (
    SELECT sum(hours) AS hours, sum(payroll_cents) AS payroll,
           sum(missing_rate_shifts) AS missing_shifts,
           sum(missing_rate_hours) AS missing_hours
    FROM daily_labor
    WHERE venue_code = $venue AND work_date BETWEEN $start AND $end
)
SELECT * FROM t, p, e, l
"""

OUTLET_SQL = """
SELECT outlet, sum(revenue_cents) AS cents FROM daily_pos
WHERE venue_code = $venue AND business_date BETWEEN $start AND $end
GROUP BY outlet ORDER BY outlet
"""

# Power BI's productivity is one hundredth below ours at Summit. Summing
# shifts rounded to 0.1 h is the candidate explanation tested here (R-004).
SHIFT_ROUNDED_HOURS_SQL = """
SELECT sum(round_even(hours, 1)), sum(round(hours, 1)) FROM fact_labor_shift
WHERE venue_code = $venue AND work_date BETWEEN $start AND $end
"""

CHANNEL_SQL = """
SELECT sales_channel, sum(ticket_revenue_cents) AS cents, sum(attendance) AS guests
FROM daily_tickets
WHERE venue_code = $venue AND business_date BETWEEN $start AND $end
GROUP BY sales_channel ORDER BY cents DESC, sales_channel
"""


def _round(value: Decimal, measure: str) -> Decimal:
    step = PRECISION.get(measure, Decimal("1"))
    return value.quantize(step, rounding=ROUND_HALF_UP)


def compare(measure: str, ours: float | None, target: float) -> dict:
    """Round ours to the target's precision and compare.

    A measure with no data is reported as "no data", never as zero.
    """
    if ours is None:
        return {
            "measure": measure,
            "ours": None,
            "target": target,
            "difference": None,
            "status": "no data",
        }
    rounded = _round(Decimal(str(ours)), measure)
    difference = rounded - Decimal(str(target))
    return {
        "measure": measure,
        "ours": ours,
        "ours_rounded": float(rounded),
        "target": target,
        "difference": float(difference),
        "status": "match" if difference == 0 else "miss",
    }


def required_misses(rows: list[dict], required: list[str]) -> list[dict]:
    """Return rows for required venues that do not match."""
    return [r for r in rows if r["venue"] in required and r["status"] != "match"]


def _dollars(cents) -> float | None:
    return None if cents is None else float(Decimal(int(cents)) / 100)


def week_actuals(con, venue: str, start: str, end: str) -> dict:
    """Return our unrounded figures for one venue and window."""
    params = {"venue": venue, "start": start, "end": end}
    cols = [d[0] for d in con.execute(WEEK_SQL, params).description]
    row = dict(zip(cols, con.execute(WEEK_SQL, params).fetchone(), strict=True))
    revenue = [row["tix"], row["fnb"], row["merch"], row["pe"]]
    total = None if None in revenue else sum(revenue)
    return {
        "attendance": None if row["attendance"] is None else int(row["attendance"]),
        "ticket_revenue": _dollars(row["tix"]),
        "fnb_revenue": _dollars(row["fnb"]),
        "merch_revenue": _dollars(row["merch"]),
        "private_events_revenue": _dollars(row["pe"]),
        "total_revenue": _dollars(total),
        "labor_hours": row["hours"],
        "payroll": _dollars(row["payroll"]),
        "payroll_missing_rate_shifts": int(row["missing_shifts"] or 0),
        "payroll_missing_rate_hours": round(row["missing_hours"] or 0, 2),
    }


def _fmt(value) -> str:
    if value is None:
        return "no data"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.2f}"


def _fmt_diff(measure: str, diff: float | None) -> str:
    if diff is None:
        return ""
    return f"{diff:+,.1f}" if measure in PRECISION else f"{diff:+,.0f}"


def _payroll_note(d: dict) -> str:
    if d["payroll_missing_rate_shifts"] == 0:
        return "Payroll is complete. Every shift has a rate."
    return (
        f"Payroll is incomplete. {d['payroll_missing_rate_shifts']} shift(s) "
        f"and {d['payroll_missing_rate_hours']:.2f} hours have no rate."
    )


def render(rows, details, window, required) -> str:
    """Return the Markdown report."""
    lines = [
        "# Reconciliation",
        "",
        f"Window {window['start']} to {window['end']}. Generated "
        f"{datetime.now():%Y-%m-%d %H:%M} from build/attractions.duckdb.",
        f"Required venues: {', '.join(required)}. Ours is unrounded. Status "
        "compares ours rounded to the target's precision.",
        "",
        "| Venue | Measure | Ours | Target | Difference | Status |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        diff = r["difference"]
        lines.append(
            f"| {r['venue']} | {r['measure']} | {_fmt(r['ours'])} | "
            f"{r['target']:,} | {_fmt_diff(r['measure'], diff)} | "
            f"{r['status']} |"
        )
    for venue, d in details.items():
        lines += [
            "",
            f"## {venue} detail",
            "",
            _payroll_note(d),
            f"Guests per labor hour: {d['guests_per_labor_hour']:.4f}. "
            "With each shift rounded to 0.1 h first, hours are "
            f"{d['shift_rounded_hours'][0]:.2f} rounding half to even and "
            f"{d['shift_rounded_hours'][1]:.2f} rounding half up, giving "
            f"{d['shift_rounded_guests_per_hour'][0]:.3f} and "
            f"{d['shift_rounded_guests_per_hour'][1]:.3f} guests per hour. Showing "
            f"{d['one_lower']:.2f} needs {d['one_lower_hours'][0]:.2f} to "
            f"{d['one_lower_hours'][1]:.2f} hours.",
            "",
            "Power BI cross-check figures: Restaurant minus Bar "
            f"{d['restaurant_minus_bar']:,.2f}, F&B as the Ancillary visual "
            f"shows it {d['fnb_as_ancillary_visual']:,.2f}, ticket "
            f"revenue without Affiliate {d['channels_without_affiliate']:,.2f}.",
            "",
            "| Outlet | Revenue |",
            "|---|---|",
        ]
        lines += [f"| {o} | {v:,.2f} |" for o, v in d["outlets"].items()]
        lines += ["", "| Sales channel | Revenue | Guests |", "|---|---|---|"]
        lines += [
            f"| {c} | {v['revenue']:,.2f} | {v['guests']:,} |"
            for c, v in d["channels"].items()
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Run the reconciliation and print the report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.environ.get("DUCKDB_PATH", "build/attractions.duckdb")),
    )
    args = parser.parse_args(argv)
    spec = json.loads(TARGETS.read_text())
    window, required = spec["window"], spec["required"]
    if not args.db.exists():
        print(f"{args.db} not found. Run `make load` first.", file=sys.stderr)
        return 1
    con = duckdb.connect(str(args.db), read_only=True)
    rows, details = [], {}
    try:
        for venue, targets in spec["venues"].items():
            ours = week_actuals(con, venue, window["start"], window["end"])
            for measure in MEASURES:
                row = compare(measure, ours[measure], targets[measure])
                rows.append({"venue": venue, **row})
            params = {"venue": venue, **window}
            outlets = con.execute(OUTLET_SQL, params).fetchall()
            channels = con.execute(CHANNEL_SQL, params).fetchall()
            half_even, half_up = con.execute(SHIFT_ROUNDED_HOURS_SQL, params).fetchone()
            per_hour = ours["attendance"] / ours["labor_hours"]
            one_lower = round(round(per_hour, 2) - 0.01, 2)
            outlet = {o: _dollars(c) for o, c in outlets}
            channel = {c: _dollars(v) for c, v, _ in channels}
            details[venue] = {
                "payroll_missing_rate_shifts": ours["payroll_missing_rate_shifts"],
                "payroll_missing_rate_hours": ours["payroll_missing_rate_hours"],
                "guests_per_labor_hour": per_hour,
                "shift_rounded_hours": [half_even, half_up],
                "shift_rounded_guests_per_hour": [
                    ours["attendance"] / half_even,
                    ours["attendance"] / half_up,
                ],
                "one_lower": one_lower,
                "one_lower_hours": [
                    ours["attendance"] / (one_lower + 0.005),
                    ours["attendance"] / (one_lower - 0.005),
                ],
                "outlets": outlet,
                "restaurant_minus_bar": round(outlet["Restaurant"] - outlet["Bar"], 2),
                "fnb_as_ancillary_visual": round(
                    ours["fnb_revenue"] - outlet["Bar"], 2
                ),
                "channels_without_affiliate": round(
                    sum(channel.values()) - channel.get("Affiliate", 0), 2
                ),
                "channels": {
                    c: {"revenue": _dollars(v), "guests": int(g)}
                    for c, v, g in channels
                },
            }
    finally:
        con.close()
    REPORTS.mkdir(parents=True, exist_ok=True)
    report = render(rows, details, window, required)
    (REPORTS / "reconciliation.md").write_text(report)
    (REPORTS / "reconciliation.json").write_text(
        json.dumps({"window": window, "rows": rows, "details": details}, indent=2)
        + "\n"
    )
    print(report)
    misses = required_misses(rows, required)
    if misses:
        names = ", ".join(f"{r['venue']} {r['measure']}" for r in misses)
        print(f"required venue misses: {names}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
