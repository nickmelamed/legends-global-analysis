from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pipeline import rules


def test_after_midnight_belongs_to_the_previous_business_day():
    ts = pd.Series(pd.to_datetime(["2026-10-05 00:33", "2026-10-04 04:00"]))
    local = rules.to_local(ts, "America/Chicago", rules.SOURCE_ZONE_LOCAL)
    assert rules.business_dates(local).tolist() == [date(2026, 10, 4)] * 2


def test_utc_timestamp_is_converted_before_the_cutoff():
    # 02:30 UTC on 09-29 is 20:30 on 09-28 in Denver (MDT, UTC-6).
    ts = pd.Series(pd.to_datetime(["2026-09-29 02:30"]))
    local = rules.to_local(ts, "America/Denver", rules.SOURCE_ZONE_UTC)
    assert local.iloc[0] == pd.Timestamp("2026-09-28 20:30")
    assert rules.business_dates(local).tolist() == [date(2026, 9, 28)]


def test_unknown_source_zone_is_refused():
    ts = pd.Series(pd.to_datetime(["2026-09-29 02:30"]))
    with pytest.raises(ValueError):
        rules.to_local(ts, "America/Denver", "probably local")


@given(st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2026, 12, 31)))
def test_business_date_is_the_calendar_date_or_the_day_before(ts):
    got = rules.business_dates(pd.Series([pd.Timestamp(ts)])).iloc[0]
    assert got in {ts.date(), ts.date() - timedelta(days=1)}
    assert (got == ts.date()) == (ts.hour >= rules.BUSINESS_DAY_CUTOFF_HOUR)


def pos_lines():
    return pd.DataFrame(
        {
            "order_id": ["O1", "O1", "O1", "O2"],
            "item_quantity": [2, 1, 1, 1],
            "item_price": [4.50, 3.00, 3.00, 12.00],
            "discount_amount": [0.50, 0.00, 0.00, 0.00],
            "is_voided": ["N", "N", "N", "Y"],
            # Order totals repeat on every line of the order.
            "subtotal": [14.50, 14.50, 14.50, 0.00],
        }
    )


def test_line_revenue_is_net_of_discount_and_excludes_voids():
    revenue = rules.pos_line_revenue_cents(pos_lines())
    assert revenue.tolist() == [850, 300, 300, 0]


def test_identical_repeated_lines_both_count():
    # Rows 1 and 2 are exact copies. The order subtotal (14.50) proves both
    # are real, so revenue is never deduplicated.
    assert rules.pos_line_revenue_cents(pos_lines()).sum() == 1450


def test_order_subtotal_check_counts_each_order_once():
    assert rules.order_subtotal_mismatches(pos_lines()) == 0
    broken = pos_lines()
    broken.loc[broken["order_id"] == "O1", "subtotal"] = 11.50
    assert rules.order_subtotal_mismatches(broken) == 1


def test_line_revenue_is_exact_in_cents():
    df = pd.DataFrame(
        {
            "item_quantity": [3] * 10,
            "item_price": [0.10] * 10,
            "discount_amount": [0.0] * 10,
            "is_voided": ["N"] * 10,
        }
    )
    assert rules.pos_line_revenue_cents(df).sum() == 300


@pytest.mark.parametrize(
    ("outlet", "department", "revenue_line"),
    [
        ("Restaurant", "Restaurant", "fnb"),
        ("Bar", "Restaurant", "fnb"),
        ("Cafe", "Cafe", "fnb"),
        ("Gift Shop", "Merchandise", "merch"),
    ],
)
def test_outlet_mapping(outlet, department, revenue_line):
    assert rules.outlet_department(outlet) == department
    assert rules.outlet_revenue_line(outlet) == revenue_line


def test_unknown_void_flag_fails_loudly():
    df = pos_lines()
    df.loc[0, "is_voided"] = "y"
    with pytest.raises(rules.UnmappedLabel):
        rules.pos_line_revenue_cents(df)


def test_unknown_outlet_fails_loudly():
    with pytest.raises(rules.UnmappedLabel):
        rules.outlet_department("Kiosk")
