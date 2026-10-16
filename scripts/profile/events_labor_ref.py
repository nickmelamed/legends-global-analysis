"""Profile the private events, labor and reference workbooks.

Run from the repo root: ``python3 scripts/profile/events_labor_ref.py``.
"""

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"
WEEK_START = pd.Timestamp("2026-09-28")
WEEK_END = pd.Timestamp("2026-10-04")
PRIOR_START = pd.Timestamp("2026-09-21")
PRIOR_END = pd.Timestamp("2026-09-27")
VENUES = ["SSD", "RTL", "TRO"]
ATTENDANCE_TARGET = {"SSD": 1849, "RTL": 883, "TRO": 771}

FREE_TEXT = {"comments", "lost_reason_name"}
LABEL_COLUMNS = {
    "private_events": [
        "record_type",
        "venue_code",
        "location_name",
        "booking_market_segment",
        "booking_status",
        "rooms",
        "selected_lead_sources",
        "owner_id",
    ],
    "labor_actual": [
        "venue_code",
        "paygroup_id",
        "location_name",
        "working_dept",
        "position",
        "rate_type",
        "is_late",
        "pay_period_flag",
        "dt_hrs",
    ],
    "labor_schedule": [
        "venue_code",
        "paygroup_id",
        "location_name",
        "department",
        "position",
    ],
    "dim_venue": ["venue_code", "timezone", "attraction_prefix", "location_id"],
    "budget_daily": ["venue_code", "department"],
    "weather_cached": ["venue_code", "wmo_weather_code"],
    "market_events_seed": ["venue_code", "category"],
}
KEYS = {
    "private_events": [["event_id"], ["lead_id"], ["booking_id"]],
    "labor_actual": [
        ["venue_code", "person_id", "date", "actual_in"],
        ["person_id", "date"],
    ],
    "labor_schedule": [
        ["venue_code", "person_id", "schedule_date", "schedule_start_time"],
        ["person_id", "schedule_date"],
    ],
    "dim_venue": [["venue_code"]],
    "budget_daily": [["venue_code", "date", "department"]],
    "weather_cached": [["venue_code", "date"]],
    "market_events_seed": [["event_id"]],
}
DATE_COLUMNS = {
    "private_events": [
        "event_date",
        "booking_definite_date",
        "booking_lost_date",
        "created_at",
        "lead_created_date",
    ],
    "labor_actual": ["date", "actual_in", "actual_out"],
    "labor_schedule": ["schedule_date"],
    "budget_daily": ["date"],
    "weather_cached": ["date"],
    "market_events_seed": ["start_date", "end_date"],
}

DEPARTMENT_MAP = {
    "operations": "Operations",
    "ops": "Operations",
    "guest services-ops": "Operations",
    "restaurant": "Restaurant",
    "f&b - restaurant": "Restaurant",
    "fnb rest": "Restaurant",
    # Every "Food & Beverage" row is a Host, Server, Busser or Bartender,
    # the same positions as the restaurant labels.
    "food & beverage": "Restaurant",
    "kitchen": "Kitchen",
    "back of house": "Kitchen",
    "boh": "Kitchen",
    "cafe": "Cafe",
    "f&b - cafe": "Cafe",
    "merchandise": "Merchandise",
    "merch": "Merchandise",
    "gift shop": "Merchandise",
    "retail": "Merchandise",
    "support": "Support",
    "security & support": "Support",
    "facilities/support": "Support",
}


def load() -> dict[str, pd.DataFrame]:
    """Read every data sheet in scope into a dict keyed by sheet name."""
    sheets = {}
    for name in [
        "03_Private_Events",
        "04_Labor",
        "05_Reference_Budget_Context",
    ]:
        book = pd.read_excel(DATA / f"{name}.xlsx", sheet_name=None)
        sheets.update({k: v for k, v in book.items() if k != "README"})
    return sheets


def heading(text: str) -> None:
    """Print a section heading."""
    print(f"\n## {text}")


def profile_sheet(name: str, df: pd.DataFrame) -> None:
    """Print row count, key uniqueness, nulls, labels and date ranges."""
    heading(f"{name}: {len(df)} rows, {df.shape[1]} columns")
    for key in KEYS.get(name, []):
        present = df.dropna(subset=key)
        dups = present.duplicated(key, keep=False).sum()
        print(
            f"key {key}: non-null {len(present)}, distinct "
            f"{len(present.drop_duplicates(key))}, rows in duplicate groups {dups}"
        )
    nulls = df.isna().sum()
    print("nulls:", nulls[nulls > 0].to_dict() or "none")
    for col in sorted(FREE_TEXT & set(df.columns)):
        lengths = df[col].dropna().astype(str).str.len()
        print(
            f"free text {col}: non-null {len(lengths)}, "
            f"length min {lengths.min()} median {lengths.median()} max {lengths.max()}"
        )
    for col in LABEL_COLUMNS.get(name, []):
        counts = df[col].map(repr).value_counts(dropna=False)
        print(f"{col} ({len(counts)} distinct): {counts.to_dict()}")
    for col in DATE_COLUMNS.get(name, []):
        print(f"{col}: {df[col].min()} to {df[col].max()}")


def canonical_department(raw: pd.Series) -> pd.Series:
    """Map raw department labels to the six reporting departments."""
    return raw.str.strip().str.lower().map(DEPARTMENT_MAP)


def label_findings(la: pd.DataFrame, ls: pd.DataFrame) -> None:
    """Print raw label variants and check that every one maps."""
    heading("H7 labels")
    for name, df, col in [
        ("labor_actual", la, "working_dept"),
        ("labor_schedule", ls, "department"),
    ]:
        mapped = canonical_department(df[col])
        print(
            f"{name}.{col}: {df[col].nunique()} raw labels, "
            f"unmapped rows {mapped.isna().sum()}"
        )
        print(
            df.assign(canon=mapped)
            .groupby("canon")[col]
            .agg(lambda s: sorted(s.map(repr).unique()))
            .to_dict()
        )
    for name, df in [("labor_actual", la), ("labor_schedule", ls)]:
        norm = df.location_name.str.strip().str.lower()
        pairs = df.assign(norm=norm).groupby("venue_code").norm.unique()
        print(f"{name}.location_name normalised per venue_code: {pairs.to_dict()}")
    dept = canonical_department(la.working_dept)
    per_position = la.assign(d=dept).groupby("position").d.nunique()
    print(
        "positions spanning more than one canonical department:",
        per_position[per_position > 1].to_dict() or "none",
    )
    in_both = set(ls.position) ^ set(la.position)
    print("positions in only one of actual/schedule:", in_both or "none")


def labor_findings(la: pd.DataFrame, ls: pd.DataFrame) -> None:
    """Print overnight, hours, earnings, rate and duplicate checks."""
    heading("H8 labor")
    clock = (la.actual_out - la.actual_in).dt.total_seconds() / 3600
    gap = (clock - la.total_hrs).round(2)
    overnight = la.actual_out.dt.normalize() > la.date
    print(
        f"overnight shifts {overnight.sum()}, rows where date != actual_in date "
        f"{(la.date != la.actual_in.dt.normalize()).sum()}"
    )
    print(
        f"total_hrs != reg_hrs + ot_hrs: "
        f"{((la.total_hrs - la.reg_hrs - la.ot_hrs).abs() > 0.005).sum()}"
    )
    print(
        f"clock hours - total_hrs: {gap.abs().le(0.01).sum()} rows within 0.01, "
        f"{gap.between(0.49, 0.51).sum()} rows near 0.5, other "
        f"{(~gap.abs().le(0.01) & ~gap.between(0.49, 0.51)).sum()}"
    )
    deducted = gap.between(0.49, 0.51)
    print(
        "0.5 h deducted by (unscheduled, clock > 6 h):",
        pd.crosstab(deducted, [la.sched_in.isna(), clock > 6]).to_dict(),
    )
    print(
        f"reg_hrs > 8: {(la.reg_hrs > 8.001).sum()}, ot rows {(la.ot_hrs > 0).sum()}, "
        f"dt_hrs non-zero {(la.dt_hrs != 0).sum()}"
    )
    ot = la[la.ot_hrs > 0]
    print(
        "ot_earnings / (ot_hrs * rate):",
        (ot.ot_earnings / (ot.ot_hrs * ot.rate)).round(1).value_counts().to_dict(),
    )
    print(
        f"reg_earnings != reg_hrs * rate: "
        f"{((la.reg_hrs * la.rate - la.reg_earnings).abs() > 0.011).sum()}, "
        f"total_earnings != reg + ot: "
        f"{((la.reg_earnings + la.ot_earnings - la.total_earnings).abs() > 0.011).sum()}"
    )
    print(f"tips > 0 rows {(la.tips > 0).sum()}, tips total {la.tips.sum():.2f}")
    missing = la[la.rate.isna()]
    print(
        f"missing rate rows {len(missing)} by venue {missing.venue_code.value_counts().to_dict()}, "
        f"earnings also null {missing.total_earnings.isna().sum()}, "
        f"hours present {missing.total_hrs.notna().sum()}, "
        f"total hours {missing.total_hrs.sum():.2f}"
    )
    per_person = la.dropna(subset=["rate"]).groupby("person_id").rate.nunique()
    print(
        f"people with a known rate elsewhere: "
        f"{missing.person_id.isin(per_person.index).sum()} of {len(missing)}; "
        f"people with more than one rate: {(per_person > 1).sum()} of {len(per_person)}"
    )
    key = ["venue_code", "person_id", "date", "actual_in"]
    dup = la[la.duplicated(key, keep=False)]
    print("duplicate business key rows:")
    shown = [
        "venue_code",
        "date",
        "actual_in",
        "actual_out",
        "total_hrs",
        "rate",
        "total_earnings",
    ]
    print(dup[shown].to_string(index=False))
    print(f"exact duplicate rows {la.duplicated(keep=False).sum()}")
    ordered = la.sort_values(["person_id", "actual_in"])
    prev_out = ordered.groupby("person_id").actual_out.shift()
    overlap = ordered[ordered.actual_in < prev_out]
    print(
        f"shifts overlapping the same person's previous shift {len(overlap)}, "
        f"of which unscheduled {overlap.sched_in.isna().sum()}"
    )
    print(f"labor_schedule exact duplicates {ls.duplicated(keep=False).sum()}")
    print(
        f"pay_period_flag Current dates {la[la.pay_period_flag == 'Current'].date.min()} "
        f"to {la[la.pay_period_flag == 'Current'].date.max()}"
    )


def week_labor(la: pd.DataFrame) -> None:
    """Print week hours and payroll under each candidate rule."""
    heading("Labor reproduction, 2026-09-28 to 2026-10-04")
    clock = (la.actual_out - la.actual_in).dt.total_seconds() / 3600
    la = la.assign(clock=clock, end_date=la.actual_out.dt.normalize())
    for venue in VENUES:
        v = la[la.venue_code == venue]
        by_start = v[v.date.between(WEEK_START, WEEK_END)]
        by_end = v[v.end_date.between(WEEK_START, WEEK_END)]
        rated = by_start[by_start.rate.notna()]
        missing = by_start[by_start.rate.isna()]
        fill = sum(
            r.total_hrs * v[(v.person_id == r.person_id) & v.rate.notna()].rate.median()
            for r in missing.itertuples()
        )
        hours = by_start.total_hrs.sum()
        rounded = by_start.total_hrs.round(1).sum()
        att = ATTENDANCE_TARGET[venue]
        print(
            f"{venue}: start-date total_hrs {hours:.2f} | end-date {by_end.total_hrs.sum():.2f} | "
            f"reg+ot {(by_start.reg_hrs + by_start.ot_hrs).sum():.2f} | "
            f"clock {by_start.clock.sum():.2f} | per-shift round(0.1) {rounded:.2f} | "
            f"rated rows only {rated.total_hrs.sum():.2f} | "
            f"scheduled rows only {by_start[by_start.sched_in.notna()].total_hrs.sum():.2f}"
        )
        print(
            f"{venue}: payroll total_earnings {by_start.total_earnings.sum():.2f} | "
            f"reg+1.5*ot recomputed {(rated.rate * (rated.reg_hrs + 1.5 * rated.ot_hrs)).sum():.2f} | "
            f"plus tips {(by_start.total_earnings.sum() + by_start.tips.sum()):.2f} | "
            f"missing-rate rows {len(missing)} ({missing.total_hrs.sum():.2f} h), "
            f"filled with person median {by_start.total_earnings.sum() + fill:.2f}"
        )
        print(
            f"{venue}: productivity {att}/{hours:.2f} = {att / hours:.4f}, "
            f"{att}/{rounded:.2f} = {att / rounded:.4f}; "
            f"labor $/guest {by_start.total_earnings.sum() / att:.4f}; "
            f"overnight shifts in week {(by_start.end_date > by_start.date).sum()}"
        )
        dept = by_start.assign(d=canonical_department(by_start.working_dept))
        table = dept.groupby("d")[["total_hrs", "total_earnings"]].sum()
        table["per_hr"] = table.total_earnings / table.total_hrs
        if venue == "SSD":
            print(table.round(2).to_string())
            print(
                "hours by day:",
                by_start.groupby("date").total_hrs.sum().round(2).tolist(),
            )
    print(
        f"hours bounds for a displayed 3.81 at SSD: {1849 / 3.815:.2f} to {1849 / 3.805:.2f}"
    )


def event_findings(pe: pd.DataFrame, bd: pd.DataFrame) -> None:
    """Print booking repetition, status and week revenue checks."""
    heading("H9 private events")
    ev = pe[pe.record_type == "EVENT"]
    print(
        "record_type x booking_status:",
        pd.crosstab(pe.record_type, pe.booking_status).to_dict(),
    )
    book = ev.groupby("booking_id").agg(
        events=("event_id", "size"),
        totals=("booking_grand_total", "nunique"),
        statuses=("booking_status", "nunique"),
        booking_total=("booking_grand_total", "first"),
        event_sum=("grand_total", "sum"),
    )
    print(
        f"bookings {len(book)}, events per booking {book.events.value_counts().to_dict()}, "
        f"booking_grand_total == sum(grand_total): "
        f"{((book.booking_total - book.event_sum).abs() < 0.01).sum()}, "
        f"bookings with mixed status {(book.statuses > 1).sum()}"
    )
    print(
        f"double-count if booking_grand_total summed over event rows: "
        f"{ev.booking_grand_total.sum() - ev.grand_total.sum():.2f}"
    )
    parts = ev.food_and_beverage_total + ev.rental_fee + ev.admin_fee
    print(
        f"grand_total == F&B + rental + admin: {((parts - ev.grand_total).abs() < 0.01).sum()} "
        f"of {len(ev)}; F&B == guest_count * price: "
        f"{((ev.guest_count * ev.price_per_person - ev.food_and_beverage_total).abs() < 0.01).sum()}; "
        f"deposit + due == grand_total: "
        f"{((ev.deposit_amount + ev.amount_due - ev.grand_total).abs() < 0.01).sum()}"
    )
    print(
        "dates present by status:",
        ev.groupby("booking_status")[["booking_definite_date", "booking_lost_date"]]
        .agg(lambda s: s.notna().sum())
        .to_dict(),
    )

    heading("Private events reproduction")
    for venue in VENUES:
        v = ev[ev.venue_code == venue]
        week = v[v.event_date.between(WEEK_START, WEEK_END)]
        definite = week[week.booking_status == "Definite"]
        prior = v[
            v.event_date.between(PRIOR_START, PRIOR_END)
            & (v.booking_status == "Definite")
        ]
        print(
            f"{venue}: definite event-level {definite.grand_total.sum():.2f} "
            f"({len(definite)} events, {definite.booking_id.nunique()} bookings) | "
            f"all statuses {week.grand_total.sum():.2f} | "
            f"definite + tentative "
            f"{week[week.booking_status.isin(['Definite', 'Tentative'])].grand_total.sum():.2f} | "
            f"booking-level per row {definite.booking_grand_total.sum():.2f} | "
            f"prior week definite {prior.grand_total.sum():.2f}"
        )
        print(
            week[
                [
                    "event_id",
                    "booking_id",
                    "booking_status",
                    "event_date",
                    "grand_total",
                    "booking_grand_total",
                ]
            ].to_string(index=False)
        )

    heading("Private events by month, SSD")
    ssd = ev[ev.venue_code == "SSD"].assign(month=ev.event_date.dt.to_period("M"))
    monthly = ssd[ssd.booking_status == "Definite"].groupby("month").grand_total.sum()
    print(monthly.loc["2025-09":"2026-12"].round(0).to_dict())
    print(
        f"max month 2025-09..2026-08 {monthly.loc['2025-09':'2026-08'].max():.0f}, "
        f"x 1.15 = {monthly.loc['2025-09':'2026-08'].max() * 1.15:.0f}"
    )
    print(
        "SSD events by month and status:",
        pd.crosstab(ssd.month, ssd.booking_status).loc["2026-07":"2026-10"].to_dict(),
    )
    budget = bd[(bd.venue_code == "SSD") & (bd.department == "Private Events")]
    print(
        "SSD private events budget by month:",
        budget.groupby(budget.date.dt.to_period("M"))
        .budget_revenue.sum()
        .loc["2026-07":"2026-10"]
        .round(0)
        .to_dict(),
    )


def coverage(sheets: dict[str, pd.DataFrame]) -> None:
    """Print missing venue-days per feed."""
    heading("H10 venue-day coverage")
    feeds = [
        ("labor_actual", "date", "2025-01-01", "2026-10-04"),
        ("labor_schedule", "schedule_date", "2025-01-01", "2026-10-18"),
        ("budget_daily", "date", "2025-01-01", "2026-12-31"),
        ("weather_cached", "date", "2025-01-01", "2026-10-04"),
    ]
    for name, col, lo, hi in feeds:
        df = sheets[name]
        for venue in VENUES:
            have = set(df.loc[df.venue_code == venue, col].dt.normalize())
            gaps = [
                d.date().isoformat() for d in pd.date_range(lo, hi) if d not in have
            ]
            print(f"{name} {venue}: {len(gaps)} missing days {gaps[:10]}")
    bd = sheets["budget_daily"]
    per_day = bd.groupby(["venue_code", "date"]).department.nunique()
    print(f"budget venue-days without all five departments: {(per_day != 5).sum()}")
    la = sheets["labor_actual"]
    rtl = la[la.venue_code == "RTL"].groupby("date").size()
    april = rtl[rtl.index.month == 4]
    print(
        f"RTL labor shifts per April day: min {april.min()} on "
        f"{april.idxmin().date()}, median {april.median()}, all-days min {rtl.min()}"
    )
    near = la[(la.venue_code == "RTL") & la.date.between("2026-04-11", "2026-04-25")]
    daily = near.groupby("date").total_hrs.agg(["count", "sum"]).round(2)
    print("RTL labor shifts and hours 2026-04-11..25:")
    print(daily.to_string())
    ev = sheets["private_events"]
    ev = ev[ev.record_type == "EVENT"]
    april_events = ev[(ev.venue_code == "RTL") & (ev.event_date.dt.month == 4)]
    print(f"RTL April events: {len(april_events)}")


def reference_findings(sheets: dict[str, pd.DataFrame]) -> None:
    """Print venue dimension, budget, weather and market seed oddities."""
    heading("H11 reference")
    print(sheets["dim_venue"].to_string(index=False))
    bd = sheets["budget_daily"]
    print(
        f"budget non-positive revenue {(bd.budget_revenue <= 0).sum()}, "
        f"budget_attendance non-null by dept "
        f"{bd.groupby('department').budget_attendance.apply(lambda s: s.notna().sum()).to_dict()}"
    )
    week = bd[bd.date.between(WEEK_START, WEEK_END)]
    print(
        "budget for the week:",
        week.pivot_table(
            index="venue_code",
            columns="department",
            values="budget_revenue",
            aggfunc="sum",
        )
        .round(0)
        .to_dict("index"),
    )
    wc = sheets["weather_cached"]
    print(wc.describe().T[["min", "max"]].to_string())
    me = sheets["market_events_seed"]
    print(
        f"market events end < start {(me.end_date < me.start_date).sum()}, "
        f"by venue {me.venue_code.value_counts().to_dict()}, "
        f"past 2026-10-05 {(me.start_date >= '2026-10-05').sum()}"
    )


def main() -> None:
    """Run every profile section in order."""
    sheets = load()
    for name, df in sheets.items():
        profile_sheet(name, df)
    la, ls = sheets["labor_actual"], sheets["labor_schedule"]
    label_findings(la, ls)
    labor_findings(la, ls)
    week_labor(la)
    event_findings(sheets["private_events"], sheets["budget_daily"])
    coverage(sheets)
    reference_findings(sheets)


if __name__ == "__main__":
    main()
