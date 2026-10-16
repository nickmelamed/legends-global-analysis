"""Business rules for the Attractions load, API and reconciliation.

Every rule that decides what a number means lives here, so the API and the
frontend never reimplement one. Evidence for each rule is in
docs/DATA_PROFILE.md and the decisions in docs/DECISIONS.md.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd


class UnmappedLabel(ValueError):
    """A source value that no rule knows how to treat."""


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


def conflicting_duplicate_loads(df: pd.DataFrame) -> int:
    """Count ``ticket_line_id`` values whose copies differ beyond ``ingestion_ts``.

    Keeping the latest load is only safe when the copies agree, so any count
    above zero must stop the load.
    """
    repeated = df[df["ticket_line_id"].duplicated(keep=False)]
    distinct = repeated.drop(columns="ingestion_ts").drop_duplicates()
    return int(distinct["ticket_line_id"].value_counts().gt(1).sum())


BUSINESS_DAY_CUTOFF_HOUR = 4
SOURCE_ZONE_UTC = "UTC"
SOURCE_ZONE_LOCAL = "local"
# NT event_time is UTC and LT event_time is venue local. POS timestamps are
# all local, since each outlet has sharp local opening hours with nothing
# outside them (H6). Ticket rows use event_date, which is already the local date.
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


def ticket_business_dates(df: pd.DataFrame) -> pd.Series:
    """Return each ticket line's business date, which is its ``event_date``.

    ``event_date`` is the local visit date in both systems. The raw NT
    ``event_time`` is UTC and would move evening visits to the next day.
    """
    return pd.to_datetime(df["event_date"]).dt.date


def ticket_event_time_mismatches(df: pd.DataFrame, timezone: str) -> int:
    """Count lines whose ``event_time``, in local time, is not on ``event_date``.

    Zero is expected. A non-zero count means a source changed its time zone.
    """
    mismatched = 0
    for source, rows in df.groupby("source_system"):
        if source not in TICKET_EVENT_TIME_ZONE:
            raise UnmappedLabel(f"source_system {source!r} is not mapped")
        local = to_local(
            pd.to_datetime(rows["event_time"]), timezone, TICKET_EVENT_TIME_ZONE[source]
        )
        mismatched += int((business_dates(local) != ticket_business_dates(rows)).sum())
    return mismatched


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


# Raw labels after strip and lower-case. "Food & Beverage" holds only Host,
# Server, Busser and Bartender shifts, the restaurant positions (H7).
LABOR_DEPARTMENT = {
    "operations": "Operations",
    "ops": "Operations",
    "guest services-ops": "Operations",
    "restaurant": "Restaurant",
    "f&b - restaurant": "Restaurant",
    "fnb rest": "Restaurant",
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


def labor_department(raw: str) -> str:
    """Return the canonical labor department for a raw label."""
    try:
        return LABOR_DEPARTMENT[raw.strip().lower()]
    except (KeyError, AttributeError):
        raise UnmappedLabel(f"labor department {raw!r} is not mapped") from None


def normalise_location(raw: str, venue_names: list[str]) -> str:
    """Return the venue name a case or whitespace variant refers to."""
    by_key = {name.lower(): name for name in venue_names}
    try:
        return by_key[raw.strip().lower()]
    except (KeyError, AttributeError):
        raise UnmappedLabel(f"location_name {raw!r} is not a known venue") from None


def labor_shift_measures(df: pd.DataFrame) -> pd.DataFrame:
    """Return work date, hours, payroll and the missing-rate flag per shift.

    A shift belongs to its start date (``date``), including overnight shifts.
    Hours are ``total_hrs``, which already carries the 0.5 h unpaid break.
    Payroll is the exported ``total_earnings``, without tips. A shift with no
    rate has no payroll (null, not zero) and marks its window incomplete,
    because rates change on almost every shift and a fill would be a guess
    (D-006).
    """
    missing = df["rate"].isna() | df["total_earnings"].isna()
    payroll = (df["total_earnings"] * 100).round().astype("Int64")
    return pd.DataFrame(
        {
            "work_date": df["date"].dt.date,
            "hours": df["total_hrs"].astype(float),
            "payroll_cents": payroll.mask(missing),
            "missing_rate": missing,
        },
        index=df.index,
    )


EVENT_RECORD_TYPES = {"EVENT", "LEAD"}
EVENT_STATUS_COUNTS = {
    "Definite": True,
    "Tentative": False,
    "Lost": False,
    "Canceled": False,
    "Lead": False,
}


def is_countable_event(record_type: str, status: str) -> bool:
    """Return whether a private events row is booked revenue (Definite events)."""
    if status not in EVENT_STATUS_COUNTS:
        raise UnmappedLabel(f"booking_status {status!r} is not mapped")
    if record_type not in EVENT_RECORD_TYPES:
        raise UnmappedLabel(f"record_type {record_type!r} is not mapped")
    return record_type == "EVENT" and EVENT_STATUS_COUNTS[status]


def private_event_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """Return countable events with their own money on their own date.

    ``booking_grand_total`` repeats on every event row of a multi-day booking,
    so it is never summed. Each event's ``grand_total`` lands on its
    ``event_date`` (H9).
    """
    keep = [
        is_countable_event(t, s)
        for t, s in zip(df["record_type"], df["booking_status"], strict=True)
    ]
    events = df.loc[keep]
    return pd.DataFrame(
        {
            "booking_id": events["booking_id"],
            "event_date": events["event_date"].dt.date,
            "revenue_cents": to_cents(events["grand_total"]),
        }
    )


# Ticketing moved from LT to NT on this date. Package names change across it,
# so last-year comparisons use package_class (H4).
CUTOVER_DATE = date(2026, 2, 3)
# 52 weeks, so a last-year window starts on the same weekday.
LAST_YEAR_OFFSET_DAYS = 364


def week_start(day: date) -> date:
    """Return the Monday of the Monday to Sunday week containing ``day``."""
    return day - timedelta(days=day.weekday())


def prior_period(start: date, end: date) -> tuple[date, date]:
    """Return the window of equal length that ends the day before ``start``."""
    length = end - start
    prior_end = start - timedelta(days=1)
    return prior_end - length, prior_end


def last_year(start: date, end: date) -> tuple[date, date]:
    """Return the same window 364 days earlier."""
    offset = timedelta(days=LAST_YEAR_OFFSET_DAYS)
    return start - offset, end - offset


def crosses_cutover(start: date, end: date) -> bool:
    """Return whether a window holds days from both ticketing systems."""
    return start < CUTOVER_DATE <= end


# Presets end on the day before "today", the last complete business day
# (D-011). days_total is the length of the whole week, month or year, so pace
# can show how far through the period the window is.
def last_week(today: date) -> tuple[date, date, int]:
    """Return the Monday to Sunday week before the week containing ``today``."""
    start = week_start(today) - timedelta(days=7)
    return start, start + timedelta(days=6), 7


def month_to_date(today: date) -> tuple[date, date, int]:
    """Return the month containing yesterday, from its first day to yesterday."""
    end = today - timedelta(days=1)
    start = end.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    return start, end, (next_month - start).days


def year_to_date(today: date) -> tuple[date, date, int]:
    """Return the year containing yesterday, from 1 January to yesterday."""
    end = today - timedelta(days=1)
    start = end.replace(month=1, day=1)
    return start, end, (start.replace(year=start.year + 1) - start).days


def last_complete_day(today: date) -> date:
    """Return yesterday, the last business day that has closed (D-011)."""
    return today - timedelta(days=1)


def elapsed_end(start: date, end: date, today: date) -> date | None:
    """Return the last day of the window that has happened, or None if none has.

    Actuals and pace cover ``start`` to this day only, so presales and booked
    future events never count as actuals.
    """
    last = last_complete_day(today)
    return min(end, last) if start <= last else None


def comparison_elapsed_end(
    start: date, elapsed: date | None, cmp_start: date | None
) -> date | None:
    """Return the comparison day that lines up with the last elapsed day.

    Both sides then cover the same number of days.
    """
    if elapsed is None or cmp_start is None:
        return None
    return cmp_start + (elapsed - start)


def comparison_crosses_cutover(
    start: date, end: date, cmp_start: date | None, cmp_end: date | None
) -> bool:
    """Return whether the current or comparison window spans the cutover.

    Package names and channels change at the cutover, so either window
    spanning it makes a name-level comparison unsafe. Package class is the
    stable key (H4).
    """
    if crosses_cutover(start, end):
        return True
    return cmp_start is not None and crosses_cutover(cmp_start, cmp_end)


# Two years, leap day included. It holds all the data (from 2025-01-01) and a
# year-on-year view, and keeps a typo such as 2062 from scanning decades.
MAX_WINDOW_DAYS = 731


def window_within_limit(start: date, end: date) -> bool:
    """Return whether a window is at most ``MAX_WINDOW_DAYS`` long."""
    return (end - start).days + 1 <= MAX_WINDOW_DAYS


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    """Return numerator / denominator, or None when either is missing or zero."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def pct_change(current: float | None, comparison: float | None) -> float | None:
    """Return the percent change from ``comparison`` to ``current``."""
    if current is None:
        return None
    change = ratio(current - (comparison or 0), comparison)
    return None if change is None else change * 100


PACE_GREEN_PCT = 100.0
PACE_AMBER_PCT = 90.0


def pace_status(pct: float | None) -> str | None:
    """Return green at 100% of plan or more, amber from 90%, red below 90%."""
    if pct is None:
        return None
    if pct >= PACE_GREEN_PCT:
        return "green"
    return "amber" if pct >= PACE_AMBER_PCT else "red"


FEED_OK = "ok"
FEED_NO_DATA = "no_data"


def feed_day_status(present: set[date], start: date, end: date) -> dict[date, str]:
    """Return ok or no_data for each day of a venue's feed.

    A day with no rows is a missing feed, shown as "no data" and never as zero
    (D-005).
    """
    days = (start + timedelta(days=i) for i in range((end - start).days + 1))
    return {d: FEED_OK if d in present else FEED_NO_DATA for d in days}


def outlet_day_value(
    outlet_has_rows: bool, venue_has_rows: bool, revenue: float | None
) -> float | None:
    """Return an outlet's revenue for a day, zero, or None for no data.

    An outlet with no rows on a day the venue's other outlets have rows was
    closed or sold nothing, so it is zero (D-007). With no rows from the
    venue at all, the feed is missing and the value is None (D-005).
    """
    if outlet_has_rows:
        return revenue
    return 0.0 if venue_has_rows else None
