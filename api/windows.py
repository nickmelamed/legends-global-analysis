"""Resolve a date preset or custom range into current and comparison windows.

Built only from the window rules in ``pipeline.rules``. Every response
carries the result, so the UI never recomputes dates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal

from fastapi import HTTPException

from pipeline import rules

Preset = Literal["last_week", "month_to_date", "year_to_date", "custom"]
CompareMode = Literal["prior_period", "last_year"]

PRESETS = {
    "last_week": rules.last_week,
    "month_to_date": rules.month_to_date,
    "year_to_date": rules.year_to_date,
}


@dataclass(frozen=True)
class Window:
    """A current window, its comparison and how much of it has happened."""

    start: date
    end: date
    days_total: int
    days_elapsed: int
    elapsed_end: date | None
    compare_mode: CompareMode | None
    comparison_start: date | None
    comparison_end: date | None
    comparison_elapsed_end: date | None
    crosses_cutover: bool

    def as_dict(self) -> dict:
        """Return the window as JSON-ready values."""
        return {
            k: v.isoformat() if isinstance(v, date) else v
            for k, v in asdict(self).items()
        }


def resolve(
    preset: Preset,
    start: date | None,
    end: date | None,
    compare: bool,
    mode: CompareMode,
    today: date,
) -> Window:
    """Return the window for a preset, or for ``start`` to ``end`` if custom.

    Days elapsed run up to yesterday, the last complete business day. Actuals,
    pace and the comparison cover those days only, and the comparison's
    elapsed part is the same number of days from its own start.
    """
    if preset == "custom":
        if start is None or end is None:
            raise HTTPException(422, "a custom range needs start and end")
        if start > end:
            raise HTTPException(422, "start is after end")
        if not rules.window_within_limit(start, end):
            raise HTTPException(
                422, f"a custom range can be at most {rules.MAX_WINDOW_DAYS} days"
            )
        days_total = (end - start).days + 1
    else:
        start, end, days_total = PRESETS[preset](today)
    elapsed_end = rules.elapsed_end(start, end, today)
    days_elapsed = (elapsed_end - start).days + 1 if elapsed_end else 0
    cmp_start = cmp_end = cmp_elapsed_end = None
    if compare:
        compare_fn = rules.prior_period if mode == "prior_period" else rules.last_year
        cmp_start, cmp_end = compare_fn(start, end)
        cmp_elapsed_end = rules.comparison_elapsed_end(start, elapsed_end, cmp_start)
    return Window(
        start=start,
        end=end,
        days_total=days_total,
        days_elapsed=days_elapsed,
        elapsed_end=elapsed_end,
        compare_mode=mode if compare else None,
        comparison_start=cmp_start,
        comparison_end=cmp_end,
        comparison_elapsed_end=cmp_elapsed_end,
        crosses_cutover=rules.comparison_crosses_cutover(
            start, end, cmp_start, cmp_end
        ),
    )
