from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pipeline import rules

DAYS = st.dates(min_value=date(2024, 1, 2), max_value=date(2027, 12, 31))


@pytest.mark.parametrize(
    "today",
    [date(2026, 10, 5), date(2026, 10, 8), date(2026, 10, 11)],
)
def test_last_week_is_the_previous_monday_to_sunday(today):
    assert rules.last_week(today) == (date(2026, 9, 28), date(2026, 10, 4), 7)


def test_month_to_date_runs_through_yesterday():
    assert rules.month_to_date(date(2026, 10, 5)) == (
        date(2026, 10, 1),
        date(2026, 10, 4),
        31,
    )


def test_month_to_date_on_the_first_is_the_previous_month():
    assert rules.month_to_date(date(2026, 3, 1)) == (
        date(2026, 2, 1),
        date(2026, 2, 28),
        28,
    )


def test_year_to_date_runs_through_yesterday():
    assert rules.year_to_date(date(2026, 10, 5)) == (
        date(2026, 1, 1),
        date(2026, 10, 4),
        365,
    )
    assert rules.year_to_date(date(2024, 3, 1))[2] == 366


@given(DAYS)
def test_presets_end_yesterday_and_fit_their_period(today):
    for preset in (rules.last_week, rules.month_to_date, rules.year_to_date):
        start, end, total = preset(today)
        assert end < today
        assert start <= end
        assert (end - start).days + 1 <= total
    start, end, _ = rules.last_week(today)
    assert start.weekday() == 0 and end.weekday() == 6
    assert rules.month_to_date(today)[1] == today - timedelta(days=1)


@pytest.mark.parametrize(
    ("num", "den", "expected"),
    [(10, 4, 2.5), (0, 4, 0.0), (10, 0, None), (None, 4, None), (10, None, None)],
)
def test_ratio_is_none_over_missing_or_zero(num, den, expected):
    assert rules.ratio(num, den) == expected


@pytest.mark.parametrize(
    ("pct", "status"),
    [
        (None, None),
        (120.0, "green"),
        (100.0, "green"),
        (99.99, "amber"),
        (90.0, "amber"),
        (89.99, "red"),
        (0.0, "red"),
    ],
)
def test_pace_status_thresholds(pct, status):
    assert rules.pace_status(pct) == status


@pytest.mark.parametrize(
    ("current", "comparison", "expected"),
    [
        (110, 100, 10.0),
        (90, 100, -10.0),
        (5, 0, None),
        (None, 100, None),
        (5, None, None),
    ],
)
def test_pct_change_is_none_without_a_comparison(current, comparison, expected):
    result = rules.pct_change(current, comparison)
    assert result == pytest.approx(expected) if expected is not None else result is None


def test_last_complete_day_is_yesterday():
    assert rules.last_complete_day(date(2026, 10, 5)) == date(2026, 10, 4)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (date(2026, 9, 28), date(2026, 10, 4), date(2026, 10, 4)),
        (date(2026, 9, 28), date(2026, 10, 31), date(2026, 10, 4)),
        (date(2026, 10, 4), date(2026, 10, 4), date(2026, 10, 4)),
        (date(2026, 10, 5), date(2026, 10, 31), None),
    ],
)
def test_elapsed_end_stops_at_yesterday(start, end, expected):
    assert rules.elapsed_end(start, end, date(2026, 10, 5)) == expected


@pytest.mark.parametrize(
    ("start", "end", "cmp", "expected"),
    [
        (
            date(2026, 9, 28),
            date(2026, 10, 4),
            (date(2025, 9, 29), date(2025, 10, 5)),
            False,
        ),
        (
            date(2026, 2, 2),
            date(2026, 2, 8),
            (date(2025, 2, 3), date(2025, 2, 9)),
            True,
        ),
        (
            date(2027, 2, 1),
            date(2027, 2, 7),
            (date(2026, 2, 2), date(2026, 2, 8)),
            True,
        ),
        (date(2026, 1, 1), date(2026, 10, 4), (None, None), True),
        (date(2026, 9, 28), date(2026, 10, 4), (None, None), False),
    ],
)
def test_comparison_crosses_cutover(start, end, cmp, expected):
    assert rules.comparison_crosses_cutover(start, end, *cmp) is expected


def test_comparison_elapsed_end_matches_the_elapsed_length():
    assert rules.comparison_elapsed_end(
        date(2026, 9, 28), date(2026, 10, 4), date(2026, 8, 25)
    ) == date(2026, 8, 31)
    assert (
        rules.comparison_elapsed_end(date(2026, 9, 28), None, date(2026, 8, 25)) is None
    )
    assert (
        rules.comparison_elapsed_end(date(2026, 9, 28), date(2026, 10, 4), None) is None
    )


@pytest.mark.parametrize(
    ("start", "end", "ok"),
    [
        (date(2025, 1, 1), date(2026, 12, 31), True),
        (date(2024, 1, 1), date(2025, 12, 31), True),
        (date(2025, 1, 1), date(2027, 1, 2), False),
        (date(2026, 10, 4), date(2026, 10, 4), True),
    ],
)
def test_window_length_is_capped_at_two_years(start, end, ok):
    assert rules.window_within_limit(start, end) is ok
