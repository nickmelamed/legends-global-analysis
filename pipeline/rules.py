"""Business rules for the Attractions load, API and reconciliation.

Every rule that decides what a number means lives here, so the API and the
frontend never reimplement one. Evidence for each rule is in
docs/DATA_PROFILE.md and the decisions in docs/DECISIONS.md.
"""

from __future__ import annotations

import pandas as pd


class UnmappedLabel(ValueError):
    """A source value that no rule knows how to treat."""


# Tickets

# Each source system has its own status vocabulary. Cancelled lines keep their
# full quantity and value and record_status is ACTIVE on every row, so the
# status text is the only cancellation signal (DATA_PROFILE.md H2).
TICKET_STATUS_CANCELLED = {
    "LT": {"In Process": False, "Redeemed": False, "No Show": False, "Cancelled": True},
    "NT": {
        "CONFIRMED": False,
        "REDEEMED": False,
        "NO_SHOW": False,
        "PART_REDEEMED": False,
        "CANCELLED": True,
    },
}

ADMISSION_CLASSES = {"INDIVIDUAL", "GROUP", "FIT", "PROMOTION"}
# Add-ons (photo, parking) and private event entries are not visits (H3).
NON_ADMISSION_CLASSES = {"NON-ADMISSION", "EVENT"}


def is_cancelled(source_system: str, status: str) -> bool:
    """Return whether a ticket status means the line was cancelled.

    A status outside the source system's own vocabulary raises
    ``UnmappedLabel``, so a new status stops the load instead of being counted.
    """
    try:
        return TICKET_STATUS_CANCELLED[source_system][status]
    except KeyError:
        raise UnmappedLabel(
            f"ticket_status {status!r} is not known for source {source_system!r}"
        ) from None


def is_countable_ticket(source_system: str, status: str, package_class: str) -> bool:
    """Return whether a ticket line counts toward attendance and ticket revenue.

    Annual Pass visits ($0), no-shows and free admission count (D-004).
    """
    if package_class in NON_ADMISSION_CLASSES:
        admission = False
    elif package_class in ADMISSION_CLASSES:
        admission = True
    else:
        raise UnmappedLabel(f"package_class {package_class!r} is not mapped")
    return admission and not is_cancelled(source_system, status)


def countable_ticket_mask(df: pd.DataFrame) -> pd.Series:
    """Return a boolean mask of countable lines.

    Needs ``source_system``, ``ticket_status`` and ``package_class`` columns.
    """
    keys = df[["source_system", "ticket_status", "package_class"]]
    decided = {k: is_countable_ticket(*k) for k in set(map(tuple, keys.to_numpy()))}
    return pd.Series(
        [decided[tuple(k)] for k in keys.to_numpy()], index=df.index, dtype=bool
    )


def dedup_ticket_loads(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Keep the latest ``ingestion_ts`` for each ``ticket_line_id``.

    Returns the deduplicated frame and the number of rows dropped. The 262
    repeated ids in the source are identical apart from ``ingestion_ts`` (H1).
    """
    out = df.sort_values(
        ["ticket_line_id", "ingestion_ts"], kind="mergesort"
    ).drop_duplicates("ticket_line_id", keep="last")
    return out.sort_index(), len(df) - len(out)


# Time

BUSINESS_DAY_CUTOFF_HOUR = 4
SOURCE_ZONE_UTC = "UTC"
SOURCE_ZONE_LOCAL = "local"
# NT event_time is UTC and LT event_time is venue local. POS timestamps are
# all local: each outlet has sharp local opening hours with nothing outside
# them (H6). Ticket rows use event_date, which is already the local date.
POS_TIMESTAMP_ZONE = SOURCE_ZONE_LOCAL
TICKET_EVENT_TIME_ZONE = {"LT": SOURCE_ZONE_LOCAL, "NT": SOURCE_ZONE_UTC}


def to_local(ts: pd.Series, timezone: str, source_zone: str) -> pd.Series:
    """Return naive venue-local timestamps.

    ``source_zone`` must say what the naive input is (``SOURCE_ZONE_UTC`` or
    ``SOURCE_ZONE_LOCAL``), so a business day is never assigned from a
    timestamp whose zone is a guess.
    """
    if source_zone == SOURCE_ZONE_LOCAL:
        return ts
    if source_zone == SOURCE_ZONE_UTC:
        return ts.dt.tz_localize("UTC").dt.tz_convert(timezone).dt.tz_localize(None)
    raise ValueError(f"unknown source zone {source_zone!r}")


def business_dates(local_ts: pd.Series) -> pd.Series:
    """Return the business date of each venue-local timestamp.

    The business day runs from 04:00 to 03:59 the next morning.
    """
    shifted = local_ts - pd.Timedelta(hours=BUSINESS_DAY_CUTOFF_HOUR)
    return shifted.dt.date


# POS

# Bar has no budget line. Restaurant plus Bar tracks the Restaurant budget,
# and both sell alcohol with a 20% gratuity (D-003).
OUTLET_DEPARTMENT = {
    "Restaurant": "Restaurant",
    "Bar": "Restaurant",
    "Cafe": "Cafe",
    "Gift Shop": "Merchandise",
}
OUTLET_REVENUE_LINE = {
    "Restaurant": "fnb",
    "Bar": "fnb",
    "Cafe": "fnb",
    "Gift Shop": "merch",
}


def outlet_department(outlet: str) -> str:
    """Return the Overview department an outlet reports under."""
    try:
        return OUTLET_DEPARTMENT[outlet]
    except KeyError:
        raise UnmappedLabel(f"outlet {outlet!r} is not mapped") from None


def outlet_revenue_line(outlet: str) -> str:
    """Return ``fnb`` or ``merch`` for an outlet."""
    try:
        return OUTLET_REVENUE_LINE[outlet]
    except KeyError:
        raise UnmappedLabel(f"outlet {outlet!r} is not mapped") from None


def to_cents(values: pd.Series) -> pd.Series:
    """Return dollar amounts as integer cents, so sums are exact."""
    return (values * 100).round().astype("int64")


def pos_line_revenue_cents(df: pd.DataFrame) -> pd.Series:
    """Return each line's net revenue in integer cents.

    Revenue is ``item_quantity * item_price - discount_amount``, and voided
    lines are zero. Identical repeated rows are real lines and are never
    removed, because the order subtotal only matches with them kept (H1, H5).
    """
    net = df["item_quantity"].astype("int64") * to_cents(df["item_price"]) - to_cents(
        df["discount_amount"]
    )
    unknown = set(df["is_voided"].unique()) - {"Y", "N"}
    if unknown:
        raise UnmappedLabel(f"is_voided values {sorted(unknown)!r} are not mapped")
    return net.where(df["is_voided"] == "N", 0)


def order_subtotal_mismatches(df: pd.DataFrame) -> int:
    """Count orders whose repeated ``subtotal`` differs from their line sum.

    ``subtotal`` repeats on every line of an order, so it is taken once per
    order. Zero is expected for every order in the source.
    """
    lines = pd.DataFrame(
        {
            "order_id": df["order_id"],
            "net": pos_line_revenue_cents(df),
            "subtotal": to_cents(df["subtotal"]),
        }
    )
    per_order = lines.groupby("order_id").agg(
        net=("net", "sum"), subtotal=("subtotal", "first")
    )
    return int((per_order["net"] != per_order["subtotal"]).sum())
