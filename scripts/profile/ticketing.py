"""Profile data/01_Ticketing.xlsx and test the ticketing reconciliation rules.

Run from the repo root: ``python3 scripts/profile/ticketing.py``.
"""

from pathlib import Path

import pandas as pd

DATA = Path("data")
TICKETING = DATA / "01_Ticketing.xlsx"
REFERENCE = DATA / "05_Reference_Budget_Context.xlsx"

WEEK = (pd.Timestamp("2026-09-28"), pd.Timestamp("2026-10-04"))
PRIOR_WEEK = (pd.Timestamp("2026-09-21"), pd.Timestamp("2026-09-27"))
HISTORY = (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-10-04"))
TARGETS = {"SSD": (1849, 61576), "RTL": (883, 23778), "TRO": (771, 20283)}
CANCELLED = {"Cancelled", "CANCELLED"}
NON_ADMISSION_CLASSES = {"NON-ADMISSION", "EVENT"}
CATEGORICAL = {
    "fact_ticket": [
        "attraction_prefix",
        "location_id",
        "merchant_id",
        "ticket_status",
        "promotional_code",
        "customer_country",
        "o_device",
        "record_status",
    ],
    "dim_package": [
        "attraction_prefix",
        "package_class",
        "internal_name",
        "ticket_type",
        "is_season_pass",
    ],
    "dim_merchant": ["merchant_name", "sales_channel"],
}


def section(title):
    """Print a section heading."""
    print(f"\n## {title}")


def load():
    """Read the ticketing sheets and the venue dimension."""
    sheets = pd.read_excel(TICKETING, sheet_name=None)
    venues = pd.read_excel(REFERENCE, sheet_name="dim_venue")
    return sheets, venues


def profile_sheet(name, df):
    """Print row count, nulls and categorical value counts for one sheet."""
    section(f"{name}: {len(df)} rows, {df.shape[1]} columns")
    print("nulls:", {c: int(n) for c, n in df.isna().sum().items() if n})
    by = "source_system" if "source_system" in df.columns else None
    for col in CATEGORICAL.get(name, []):
        counts = (
            df.groupby(by)[col].value_counts(dropna=False)
            if by
            else df[col].value_counts(dropna=False)
        )
        print(f"{col}:", counts.to_dict())


def profile_keys(sheets):
    """Print candidate key uniqueness for each sheet."""
    section("Candidate keys")
    fact = sheets["fact_ticket"]
    print("fact_ticket.ticket_line_id unique:", fact.ticket_line_id.is_unique)
    print("fact_ticket distinct ticket_line_id:", fact.ticket_line_id.nunique())
    print("fact_ticket exact duplicate rows:", int(fact.duplicated().sum()))
    print("dim_package.package_id unique:", sheets["dim_package"].package_id.is_unique)
    print(
        "dim_merchant.merchant_id unique:",
        sheets["dim_merchant"].merchant_id.is_unique,
    )
    joined = fact.merge(
        sheets["dim_package"][["package_id", "attraction_prefix", "source_system"]],
        on="package_id",
        how="left",
        suffixes=("", "_pkg"),
    )
    print("fact rows with unknown package:", int(joined.source_system_pkg.isna().sum()))
    print(
        "fact rows whose package belongs to another venue or system:",
        int(
            (
                (joined.attraction_prefix != joined.attraction_prefix_pkg)
                | (joined.source_system != joined.source_system_pkg)
            ).sum()
        ),
    )
    unknown = ~fact.merchant_id.isin(sheets["dim_merchant"].merchant_id)
    print("fact rows with unknown merchant:", int(unknown.sum()))


def profile_dates(fact):
    """Print date ranges per source system."""
    section("Date ranges by source_system")
    cols = ["event_date", "event_time", "date_sold", "ingestion_ts"]
    print(fact.groupby("source_system")[cols].agg(["min", "max"]).T.to_string())


def profile_duplicates(fact):
    """Print duplicate ticket_line_id loads and whether their content differs."""
    section("H1 duplicate loads")
    dup = fact[fact.ticket_line_id.duplicated(keep=False)]
    print("rows:", len(dup), "ids:", dup.ticket_line_id.nunique())
    print(
        "copies per id:", dup.groupby("ticket_line_id").size().value_counts().to_dict()
    )
    content = [c for c in fact.columns if c != "ingestion_ts"]
    differing = (dup.groupby("ticket_line_id")[content].nunique() > 1).sum()
    print(
        "columns differing within a duplicated id:", differing[differing > 0].to_dict()
    )
    print(
        "by venue and event_date:",
        dup.groupby(["attraction_prefix", "event_date"])
        .ticket_line_id.nunique()
        .to_dict(),
    )
    print("ingestion_ts of duplicates:", dup.ingestion_ts.value_counts().to_dict())
    print("example:", sorted(dup.ticket_line_id.unique())[:3])


def dedupe(fact):
    """Keep the latest ingested row per ticket_line_id."""
    return fact.sort_values("ingestion_ts").drop_duplicates(
        "ticket_line_id", keep="last"
    )


def enrich(fact, sheets):
    """Join package and merchant attributes onto the fact rows."""
    pkg = sheets["dim_package"][
        ["package_id", "package_class", "internal_name", "ticket_type"]
    ]
    return fact.merge(pkg, on="package_id").merge(
        sheets["dim_merchant"], on="merchant_id"
    )


def profile_status(fact):
    """Print how cancelled and zero-value lines look in each source system."""
    section("H2 status vocabularies and value signals")
    stats = fact.assign(
        zero_value=fact.ticket_value == 0,
        negative=(fact.quantity < 0) | (fact.ticket_value < 0),
    )
    print(
        stats.groupby(["source_system", "ticket_status"])
        .agg(
            lines=("quantity", "size"),
            qty=("quantity", "sum"),
            value=("ticket_value", "sum"),
            zero_value=("zero_value", "sum"),
            negative=("negative", "sum"),
        )
        .round(2)
        .to_string()
    )
    print("record_status values:", fact.record_status.value_counts().to_dict())
    zero = stats[stats.zero_value]
    print("zero-value lines by package:", zero.internal_name.value_counts().to_dict())


def profile_packages(fact):
    """Print what non-admission packages carry in quantity and value."""
    section("H3 non-admission packages")
    print(
        fact.groupby(["package_class", "ticket_type"])
        .agg(
            lines=("quantity", "size"),
            qty=("quantity", "sum"),
            value=("ticket_value", "sum"),
        )
        .round(2)
        .to_string()
    )


def profile_cutover(sheets, fact):
    """Print package names per stable key and the pre-cutover price change."""
    section("H4 cutover")
    pkg = sheets["dim_package"]
    names = pkg[pkg.attraction_prefix == "SSD"].pivot_table(
        index=["internal_name", "package_class"],
        columns="source_system",
        values="package_name",
        aggfunc="first",
    )
    print(names.to_string())
    print(
        "package_class and internal_name identical across LT and NT:",
        (
            pkg.groupby(["attraction_prefix", "internal_name"]).package_class.nunique()
            == 1
        ).all(),
    )
    print(
        "sales_channel share by system:\n",
        pd.crosstab(fact.sales_channel, fact.source_system, normalize="columns")
        .round(3)
        .to_string(),
    )
    adult = fact[(fact.internal_name == "ga_adult") & (fact.attraction_prefix == "SSD")]
    unit = (adult.ticket_value / adult.quantity).round(2)
    keys = [adult.source_system, adult.event_date.dt.year]
    print(
        "SSD ga_adult unit price by system and event year:",
        unit.groupby(keys).value_counts().to_dict(),
    )
    ratio = (fact.retail_amount / fact.quantity).round(2)
    print(
        "retail_amount per guest by system (top values):",
        ratio.groupby(fact.source_system)
        .value_counts()
        .groupby(level=0)
        .head(4)
        .to_dict(),
    )
    print(
        "share of lines where ticket_value == retail_amount:",
        (fact.ticket_value == fact.retail_amount).mean().round(3),
    )


def profile_timezones(fact, venues):
    """Print whether event_time is local or UTC in each source system."""
    section("Timezone of event_time")
    tz = venues.set_index("attraction_prefix").timezone
    for system, rows in fact.groupby("source_system"):
        same_date = (rows.event_time.dt.normalize() == rows.event_date).mean()
        local = [
            ts.tz_localize("UTC").tz_convert(tz[prefix]).tz_localize(None)
            for ts, prefix in zip(rows.event_time, rows.attraction_prefix, strict=True)
        ]
        local = pd.Series(local, index=rows.index)
        utc_same = (local.dt.normalize() == rows.event_date).mean()
        print(
            f"{system}: event_time date == event_date {same_date:.3f}; "
            f"as UTC converted to venue time == event_date {utc_same:.3f}; "
            f"raw hours {sorted(rows.event_time.dt.hour.unique())}"
        )


def profile_missing_days(fact):
    """Print venue-days in the history window with no ticket rows."""
    section("H10 venue-days with no ticket rows")
    days = pd.date_range(*HISTORY)
    for prefix in TARGETS:
        seen = set(fact.loc[fact.attraction_prefix == prefix, "event_date"])
        missing = [d.date().isoformat() for d in days if d not in seen]
        print(f"{prefix} 2025-01-01..2026-10-04: {missing}")
    daily = (
        fact[fact.event_date <= HISTORY[1]]
        .groupby(["attraction_prefix", "event_date"])
        .size()
    )
    print("lowest line counts per venue-day:", daily.nsmallest(5).to_dict())


def countable(fact, drop_cancelled=True, drop_non_admission=True):
    """Return lines that count as admissions under the chosen rules."""
    keep = pd.Series(True, index=fact.index)
    if drop_cancelled:
        keep &= ~fact.ticket_status.isin(CANCELLED)
    if drop_non_admission:
        keep &= ~fact.package_class.isin(NON_ADMISSION_CLASSES)
    return fact[keep]


def in_window(fact, window, date_col="event_date"):
    """Return rows whose date column falls in the inclusive window."""
    return fact[(fact[date_col] >= window[0]) & (fact[date_col] <= window[1])]


def reproduce(raw, clean):
    """Print attendance and revenue under each candidate rule combination."""
    section("Reproduction of the reconciliation week")
    raw = raw.assign(utc_date=raw.event_time.dt.normalize())
    clean = clean.assign(utc_date=clean.event_time.dt.normalize())
    for prefix, (target_att, target_rev) in TARGETS.items():
        print(f"{prefix} target attendance {target_att} revenue {target_rev}")
        for dedup, base in (("dedup", clean), ("raw", raw)):
            for date_col in ("event_date", "utc_date"):
                for cancel in (True, False):
                    for non_adm in (True, False):
                        rows = countable(base, cancel, non_adm)
                        rows = in_window(
                            rows[rows.attraction_prefix == prefix], WEEK, date_col
                        )
                        att, rev = int(rows.quantity.sum()), rows.ticket_value.sum()
                        hit = att == target_att and round(rev) == target_rev
                        print(
                            f"  {dedup:5} {date_col:10} drop_cancelled={cancel!s:5} "
                            f"drop_addon_event={non_adm!s:5} attendance={att:5} "
                            f"revenue={rev:10.2f} gap_att={att - target_att:+4} "
                            f"gap_rev={rev - target_rev:+9.2f}{'  MATCH' if hit else ''}"
                        )


def cross_checks(clean):
    """Print Summit daily attendance, channel revenue and comparison figures."""
    section("Summit cross-checks against the Power BI export")
    ssd = countable(clean[clean.attraction_prefix == "SSD"])
    cal = in_window(ssd, (pd.Timestamp("2026-08-31"), WEEK[1])).groupby("event_date")
    print("attendance calendar, five weeks Mon-Sun:")
    print(cal.quantity.sum().to_numpy().reshape(5, 7))
    week = in_window(ssd, WEEK)
    by_channel = week.groupby("sales_channel").agg(
        revenue=("ticket_value", "sum"),
        attendance=("quantity", "sum"),
        lines=("ticket_line_id", "size"),
    )
    by_channel["atp"] = by_channel.revenue / by_channel.attendance
    print(by_channel.sort_values("revenue", ascending=False).round(2).to_string())
    top7 = by_channel.revenue.nlargest(7).sum()
    print(f"total {by_channel.revenue.sum():.2f}; top 7 channels {top7:.2f}")
    affiliate = week[week.sales_channel == "Affiliate"]
    print("Affiliate lines:", affiliate.ticket_line_id.tolist())
    prior = in_window(ssd, PRIOR_WEEK)
    print(
        f"prior week attendance {prior.quantity.sum()} revenue {prior.ticket_value.sum():.2f}; "
        f"change {week.quantity.sum() / prior.quantity.sum() - 1:.4f} / "
        f"{week.ticket_value.sum() / prior.ticket_value.sum() - 1:.4f}; "
        f"ATP {week.ticket_value.sum() / week.quantity.sum():.2f}"
    )
    mix = week.groupby("package_class").ticket_value.sum() / week.ticket_value.sum()
    print("revenue mix by package_class:", mix.round(3).to_dict())
    premium = week.ticket_type != "GENERAL ADMISSION"
    same_day = week.date_sold.dt.normalize() == week.event_date
    print(
        f"premium share qty {week[premium].quantity.sum() / week.quantity.sum():.3f} "
        f"lines {premium.mean():.3f}; same-day share qty "
        f"{week[same_day].quantity.sum() / week.quantity.sum():.3f} lines {same_day.mean():.3f}; "
        f"guests per order {week.quantity.sum() / week.order_id.nunique():.2f}"
    )


def main():
    """Run every profile and print the figures."""
    sheets, venues = load()
    print("README:", sheets["README"].iloc[:, 0].dropna().tolist())
    for name in ("fact_ticket", "dim_package", "dim_merchant"):
        profile_sheet(name, sheets[name])
    raw = sheets["fact_ticket"]
    profile_keys(sheets)
    profile_dates(raw)
    profile_duplicates(raw)
    raw_enriched = enrich(raw, sheets)
    clean = enrich(dedupe(raw), sheets)
    print(f"dedup dropped {len(raw) - len(clean)} rows")
    profile_status(clean)
    profile_packages(clean)
    profile_cutover(sheets, clean)
    profile_timezones(clean, venues)
    profile_missing_days(clean)
    reproduce(raw_enriched, clean)
    cross_checks(clean)


if __name__ == "__main__":
    main()
