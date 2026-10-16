from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pipeline import rules

DAYS = st.dates(min_value=date(2024, 1, 1), max_value=date(2027, 12, 31))


@pytest.mark.parametrize(
    ("day", "monday"),
    [
        (date(2026, 9, 28), date(2026, 9, 28)),
        (date(2026, 10, 4), date(2026, 9, 28)),
        (date(2026, 10, 5), date(2026, 10, 5)),
    ],
)
def test_week_runs_monday_to_sunday(day, monday):
    assert rules.week_start(day) == monday


def test_prior_period_is_the_preceding_window_of_equal_length():
    assert rules.prior_period(date(2026, 9, 28), date(2026, 10, 4)) == (
        date(2026, 9, 21),
        date(2026, 9, 27),
    )
    assert rules.prior_period(date(2026, 10, 1), date(2026, 10, 4)) == (
        date(2026, 9, 27),
        date(2026, 9, 30),
    )


def test_last_year_is_364_days_back():
    assert rules.last_year(date(2026, 9, 28), date(2026, 10, 4)) == (
        date(2025, 9, 29),
        date(2025, 10, 5),
    )


@given(DAYS, st.integers(min_value=0, max_value=400))
def test_comparison_windows_keep_length_and_weekday(start, length):
    end = start + timedelta(days=length)
    for cmp_start, cmp_end in (
        rules.prior_period(start, end),
        rules.last_year(start, end),
    ):
        assert cmp_end - cmp_start == end - start
    ly_start, _ = rules.last_year(start, end)
    assert ly_start.weekday() == start.weekday()
    prior_start, prior_end = rules.prior_period(start, end)
    assert prior_end == start - timedelta(days=1)


@pytest.mark.parametrize(
    ("start", "end", "crosses"),
    [
        (date(2026, 1, 27), date(2026, 2, 9), True),
        (date(2026, 2, 3), date(2026, 2, 9), False),
        (date(2026, 1, 27), date(2026, 2, 2), False),
    ],
)
def test_crosses_cutover(start, end, crosses):
    assert rules.crosses_cutover(start, end) is crosses


@pytest.mark.parametrize(
    ("outlet_rows", "venue_rows", "revenue", "expected"),
    [
        (True, True, 125.0, 125.0),
        # A quiet Bar on a day its venue traded is a real zero (D-007).
        (False, True, None, 0.0),
        # No rows from the venue that day is a missing feed (D-005).
        (False, False, None, None),
    ],
)
def test_outlet_day_value(outlet_rows, venue_rows, revenue, expected):
    assert rules.outlet_day_value(outlet_rows, venue_rows, revenue) == expected


def test_missing_venue_day_is_no_data_not_zero():
    present = {date(2026, 4, 17), date(2026, 4, 19)}
    status = rules.feed_day_status(present, date(2026, 4, 17), date(2026, 4, 19))
    assert status == {
        date(2026, 4, 17): rules.FEED_OK,
        date(2026, 4, 18): rules.FEED_NO_DATA,
        date(2026, 4, 19): rules.FEED_OK,
    }
