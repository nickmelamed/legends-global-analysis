"""Revenue, attendance and per cap by day, week or month."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Literal

from api.queries import daily_revenue
from api.scope import Scope
from api.windows import Window
from pipeline import rules

Grain = Literal["day", "week", "month"]

BUCKET = {
    "day": lambda d: d,
    "week": rules.week_start,
    "month": lambda d: d.replace(day=1),
}
BUCKET_DAYS = {
    "day": lambda d: 1,
    "week": lambda d: 7,
    "month": lambda d: monthrange(d.year, d.month)[1],
}


def series(
    scope: Scope, start: date, end: date, grain: Grain, shift: timedelta
) -> list[dict]:
    """Return one point per bucket, bucketing each day on ``day + shift``.

    The current series has no shift. The comparison is shifted onto the
    current dates, so its buckets hold the same relative days as the current
    ones and the two pair up. A bucket with a no-data day sums its other days
    and sets ``data_gap``, so the UI can mark it instead of drawing a dip. A
    bucket with no data has None values. A bucket shorter than its week or
    month is ``partial``.
    """
    buckets: dict[date, list[dict]] = {}
    for day in daily_revenue(scope, start, end):
        buckets.setdefault(BUCKET[grain](day["date"] + shift), []).append(day)
    points = []
    for bucket_start, days in buckets.items():
        present = [d for d in days if d["cents"] is not None]
        cents = sum(d["cents"] for d in present) if present else None
        guests = sum(d["attendance"] for d in present) if present else None
        per_cap = rules.ratio(cents, guests)
        points.append(
            {
                "bucket_start": bucket_start.isoformat(),
                "first_day": days[0]["date"].isoformat(),
                "last_day": days[-1]["date"].isoformat(),
                "days": len(days),
                "partial": len(days) < BUCKET_DAYS[grain](bucket_start),
                "revenue": None if cents is None else round(cents / 100, 2),
                "attendance": guests,
                "per_cap": None if per_cap is None else round(per_cap / 100, 2),
                "data_gap": len(present) < len(days),
                "no_data_days": len(days) - len(present),
            }
        )
    return points


def build(scope: Scope, window: Window, grain: Grain) -> dict:
    """Return the current series to yesterday and the comparison beside it.

    Package class and channel filters do not apply, since the trend is total
    revenue (D-010).
    """
    current, comparison = [], None
    if window.elapsed_end:
        current = series(scope, window.start, window.elapsed_end, grain, timedelta(0))
    if window.comparison_start:
        comparison = []
        if window.comparison_elapsed_end:
            comparison = series(
                scope,
                window.comparison_start,
                window.comparison_elapsed_end,
                grain,
                window.start - window.comparison_start,
            )
    return {
        "venues": list(scope.venues),
        "window": window.as_dict(),
        "grain": grain,
        "ticket_filters_apply": False,
        "current": current,
        "comparison": comparison,
    }
