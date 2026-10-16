"""Profile data/02_POS_FandB_Merch.xlsx (sheet pos_order_lines).

Run from the repo root: python3 scripts/profile/pos.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
POS = ROOT / "data" / "02_POS_FandB_Merch.xlsx"
REF = ROOT / "data" / "05_Reference_Budget_Context.xlsx"
WEEK = (pd.Timestamp("2026-09-28"), pd.Timestamp("2026-10-04"))
PRIOR = (pd.Timestamp("2026-09-21"), pd.Timestamp("2026-09-27"))
TARGETS = {"SSD": (9230, 6957), "RTL": (3531, 2586), "TRO": (2769, 1979)}
LABEL_COLUMNS = [
    "venue_code",
    "outlet",
    "product_name",
    "product_category",
    "item_quantity",
    "is_voided",
    "voided_reason",
    "tender_type",
]

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def section(title):
    """Print a section heading."""
    print(f"\n## {title}\n")


def load():
    """Load POS lines and derive revenue and business-day columns."""
    df = pd.read_excel(POS, sheet_name="pos_order_lines")
    df["gross"] = df["item_quantity"] * df["item_price"]
    df["net"] = df["gross"] - df["discount_amount"]
    df["voided"] = df["is_voided"].eq("Y")
    df["exact_dup"] = df.duplicated(subset=list(df.columns[:16]))
    df["dept"] = df["outlet"].map(lambda o: "merch" if o == "Gift Shop" else "fb")
    df["cal_day"] = df["order_created_date"].dt.normalize()
    df["biz_day"] = (df["order_created_date"] - pd.Timedelta(hours=4)).dt.normalize()
    return df


def profile_columns(df):
    """Print row count, nulls and distinct values of label columns."""
    section("Shape and nulls")
    print("rows", len(df), "orders", df["order_id"].nunique())
    print(df.iloc[:, :16].isna().sum().to_string())
    section("Distinct values")
    for col in LABEL_COLUMNS:
        print(col, df[col].value_counts(dropna=False).to_dict())
    print("outlet x category")
    print(pd.crosstab(df["outlet"], df["product_category"]))
    print(
        "order_id prefix != venue_code",
        (df["order_id"].str[:3] != df["venue_code"]).sum(),
    )
    prices = df.groupby(["venue_code", "product_name"])["item_price"].nunique()
    print("distinct prices per venue+product", prices.value_counts().to_dict())
    print("non-zero seconds", (df["order_created_date"].dt.second != 0).sum())
    section("Date ranges per venue and outlet")
    print(
        df.groupby(["venue_code", "outlet"])["order_created_date"]
        .agg(["min", "max", "count"])
        .to_string()
    )


def order_consistency(df):
    """Check that order-level columns repeat and match line sums."""
    section("H5 order-level columns")
    grouped = df.groupby("order_id")
    for col in ["venue_code", "outlet", "order_created_date", "tender_type"]:
        print(col, "orders with >1 value", (grouped[col].nunique() > 1).sum())
    for col in ["subtotal", "tax", "gratuity", "final_total"]:
        print(col, "orders with >1 value", (grouped[col].nunique() > 1).sum())
    orders = grouped[["subtotal", "tax", "gratuity", "final_total", "outlet"]].first()
    total_gap = orders["final_total"] - orders[["subtotal", "tax", "gratuity"]].sum(1)
    print(
        "orders where final_total != subtotal+tax+gratuity",
        (total_gap.abs() > 0.005).sum(),
    )
    rules = {
        "all lines, net": (df.index == df.index, "net"),
        "non-void, net": (~df["voided"], "net"),
        "non-void, gross": (~df["voided"], "gross"),
        "non-void, net, exact dups dropped": (~df["voided"] & ~df["exact_dup"], "net"),
    }
    for name, (mask, col) in rules.items():
        line_sum = (
            df[mask].groupby("order_id")[col].sum().reindex(orders.index, fill_value=0)
        )
        bad = ((line_sum - orders["subtotal"]).abs() > 0.005).sum()
        print(f"subtotal == sum({name}): mismatched orders {bad} of {len(orders)}")
    rate = (orders["gratuity"] / orders["subtotal"]).round(2)
    print("gratuity/subtotal by outlet")
    print(pd.crosstab(orders["outlet"], rate).to_string())


def duplicates(df):
    """Report exact duplicate lines and whether the POS subtotal counts them."""
    section("H1 duplicate lines")
    print("no ingestion or load timestamp column exists:", list(df.columns[:16]))
    print("exact duplicate rows (beyond first)", df["exact_dup"].sum())
    dups = df[df["exact_dup"]]
    print("by venue", dups["venue_code"].value_counts().to_dict())
    print("orders containing an exact duplicate", dups["order_id"].nunique())
    print("example ids", dups["order_id"].head(5).tolist())
    same_key = df.duplicated(["order_id", "product_name"]).sum()
    print("rows repeating order_id+product_name (any content)", same_key)
    ssd_week = in_week(df[df["venue_code"].eq("SSD") & df["exact_dup"] & ~df["voided"]])
    print("SSD week non-void net in exact-dup rows", round(ssd_week["net"].sum(), 2))


def in_week(df, day="biz_day", window=WEEK):
    """Return rows whose day falls in the window."""
    return df[df[day].between(*window)]


def timezones(df):
    """Show the hour profile and the effect of the 4 AM cutoff."""
    section("H6 timestamps")
    print(pd.crosstab(df["order_created_date"].dt.hour, df["venue_code"]).to_string())
    late = df[df["order_created_date"].dt.hour < 4]
    print("rows before 04:00", len(late), late["venue_code"].value_counts().to_dict())
    print(
        "rows between 02:00 and 08:59",
        df["order_created_date"].dt.hour.between(2, 8).sum(),
    )
    live = df[~df["voided"]]
    for venue in TARGETS:
        v = live[live["venue_code"].eq(venue)]
        cal = in_week(v, "cal_day")["net"].sum()
        biz = in_week(v)["net"].sum()
        moved = v[v["cal_day"] != v["biz_day"]]
        moved_week = moved[
            moved["cal_day"].between(*WEEK) | moved["biz_day"].between(*WEEK)
        ]
        print(
            f"{venue} week net calendar-day {cal:.2f} business-day {biz:.2f} "
            f"rows moved {len(moved_week)} "
            f"ids {moved_week['order_id'].unique().tolist()}"
        )


def missing_days(df):
    """List venue-days and venue-outlet-days with no POS rows."""
    section("H10 missing venue-days (business days 2025-01-01..2026-10-04)")
    days = pd.date_range("2025-01-01", "2026-10-04")
    for venue, rows in df.groupby("venue_code"):
        gap = days.difference(rows["biz_day"].unique())
        print(venue, "all outlets", len(gap), [d.strftime("%Y-%m-%d") for d in gap])
        for outlet, orows in rows.groupby("outlet"):
            gap = days.difference(orows["biz_day"].unique())
            print(f"  {outlet}: {len(gap)}", [d.strftime("%Y-%m-%d") for d in gap])


def reproduce(df):
    """Compute week F&B and merch under each candidate rule combination."""
    section("Week F&B / merch under candidate rules (targets " + str(TARGETS) + ")")
    for day in ["biz_day", "cal_day"]:
        for drop_dups in [False, True]:
            for drop_voids in [True, False]:
                for col in ["net", "gross"]:
                    rows = in_week(df, day)
                    if drop_dups:
                        rows = rows[~rows["exact_dup"]]
                    if drop_voids:
                        rows = rows[~rows["voided"]]
                    got = rows.groupby(["venue_code", "dept"])[col].sum().unstack()
                    cells = " ".join(
                        f"{v} {got.loc[v, 'fb']:.2f}/{got.loc[v, 'merch']:.2f}"
                        for v in TARGETS
                    )
                    tag = f"{day} dups={'drop' if drop_dups else 'keep'} "
                    tag += f"voids={'excl' if drop_voids else 'incl'} {col}"
                    print(f"{tag:42s} {cells}")
    orders = in_week(df).drop_duplicates("order_id")
    orders = orders.assign(
        sub_grat=orders["subtotal"] + orders["gratuity"],
        sub_tax=orders["subtotal"] + orders["tax"],
    )
    for col in ["subtotal", "sub_grat", "sub_tax", "final_total"]:
        got = orders.groupby(["venue_code", "dept"])[col].sum().unstack()
        cells = " ".join(
            f"{v} {got.loc[v, 'fb']:.2f}/{got.loc[v, 'merch']:.2f}" for v in TARGETS
        )
        print(f"{'biz_day order-level ' + col:42s} {cells}")


def ancillary(df):
    """Break down the Summit week to compare with the Ancillary visual."""
    section("Ancillary visual cross-check (Summit, business-day week, non-void net)")
    live = df[~df["voided"] & df["venue_code"].eq("SSD")]
    week = in_week(live)
    print(
        week.pivot_table(
            "net", "outlet", "product_category", "sum", margins=True
        ).round(2)
    )
    print(week.pivot_table("net", "biz_day", "outlet", "sum", margins=True).round(2))
    prior = in_week(live, window=PRIOR).groupby("outlet")["net"].sum()
    by_outlet = week.groupby("outlet")["net"].sum()
    total, bar = by_outlet.sum(), by_outlet["Bar"]
    print("week by outlet", by_outlet.round(2).to_dict(), "total", round(total, 2))
    print("prior by outlet", prior.round(2).to_dict(), "total", round(prior.sum(), 2))
    print("restaurant minus bar", round(by_outlet["Restaurant"] - bar, 2))
    print(
        "total minus bar",
        round(total - bar, 2),
        "per cap /1849",
        round((total - bar) / 1849, 2),
    )
    print("total per cap /1849", round(total / 1849, 2))
    growth = (total - bar) / (prior.sum() - prior["Bar"]) - 1
    print("growth of (total - bar) vs prior", f"{growth:.1%}")
    print("growth of total vs prior", f"{total / prior.sum() - 1:.1%}")
    orders = week.drop_duplicates("order_id")
    print("orders", len(orders), "orders excl bar", (orders["outlet"] != "Bar").sum())
    print("net / orders", round(total / len(orders), 2))
    print("final_total / orders", round(orders["final_total"].sum() / len(orders), 2))


def main():
    """Run every profile section."""
    df = load()
    profile_columns(df)
    duplicates(df)
    order_consistency(df)
    timezones(df)
    missing_days(df)
    reproduce(df)
    ancillary(df)
    venues = pd.read_excel(REF, sheet_name="dim_venue")
    section("dim_venue")
    print(venues[["venue_code", "venue_name", "timezone"]].to_string(index=False))


if __name__ == "__main__":
    main()
