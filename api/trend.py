"""Revenue, attendance and per cap by day, week or month."""

from __future__ import annotations

from datetime import date
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


def series(scope: Scope, start: date, end: date, grain: Grain) -> list[dict]:
    """Return one point per bucket.

    A no-data day is None. A bucket that holds one keeps the sum of its other
    days and sets ``data_gap``, so the UI can mark it instead of drawing a dip.
    A bucket with no data at all is None.
    """
    buckets: dict[date, list[dict]] = {}
    for day in daily_revenue(scope, start, end):
        buckets.setdefault(BUCKET[grain](day["date"]), []).append(day)
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
                "revenue": None if cents is None else round(cents / 100, 2),
                "attendance": guests,
                "per_cap": None if per_cap is None else round(per_cap / 100, 2),
                "data_gap": len(present) < len(days),
                "no_data_days": len(days) - len(present),
            }
        )
    return points


def build(scope: Scope, window: Window, grain: Grain) -> dict:
    """Return the current series to yesterday and the full comparison series.

    Comparison points pair with current points by position. Package class and
    channel filters do not apply, since the trend is total revenue (D-010).
    """
    current = (
        series(scope, window.start, window.elapsed_end, grain)
        if window.elapsed_end
        else []
    )
    comparison = (
        series(scope, window.comparison_start, window.comparison_end, grain)
        if window.comparison_start
        else None
    )
    return {
        "venues": list(scope.venues),
        "window": window.as_dict(),
        "grain": grain,
        "ticket_filters_apply": False,
        "current": current,
        "comparison": comparison,
    }
