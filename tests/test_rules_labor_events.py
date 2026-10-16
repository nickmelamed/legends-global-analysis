from datetime import date

import pandas as pd
import pytest

from pipeline import rules


@pytest.mark.parametrize(
    ("raw", "department"),
    [
        ("operations ", "Operations"),
        ("OPS", "Operations"),
        ("Guest Services-Ops", "Operations"),
        ("Food & Beverage", "Restaurant"),
        ("FNB Rest", "Restaurant"),
        ("BOH", "Kitchen"),
        ("Cafe ", "Cafe"),
        ("F&B - Cafe", "Cafe"),
        ("Gift Shop", "Merchandise"),
        ("Retail", "Merchandise"),
        ("Facilities/Support", "Support"),
    ],
)
def test_labor_department_labels_map(raw, department):
    assert rules.labor_department(raw) == department


def test_unmapped_labor_department_fails_loudly():
    with pytest.raises(rules.UnmappedLabel):
        rules.labor_department("Valet")


def test_location_variants_normalise_to_the_venue_name():
    names = ["Summit Sky Deck", "Riverbend Tower Lookout"]
    assert rules.normalise_location("SUMMIT SKY DECK", names) == "Summit Sky Deck"
    assert rules.normalise_location("summit sky deck ", names) == "Summit Sky Deck"
    with pytest.raises(rules.UnmappedLabel):
        rules.normalise_location("Summit Deck", names)


def shifts():
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-10-03", "2026-10-02", "2026-10-02"]),
            "actual_in": pd.to_datetime(
                ["2026-10-03 22:00", "2026-10-02 09:00", "2026-10-02 12:00"]
            ),
            "actual_out": pd.to_datetime(
                ["2026-10-04 06:00", "2026-10-02 17:30", "2026-10-02 17:00"]
            ),
            "rate": [20.0, 18.0, None],
            "total_hrs": [7.5, 8.0, 4.5],
            "total_earnings": [150.0, 144.0, None],
            "tips": [0.0, 35.0, 0.0],
        }
    )


def test_overnight_shift_stays_on_its_start_date():
    out = rules.labor_shift_measures(shifts())
    assert out["work_date"].tolist() == [
        date(2026, 10, 3),
        date(2026, 10, 2),
        date(2026, 10, 2),
    ]


def test_hours_are_paid_hours_and_tips_are_not_payroll():
    out = rules.labor_shift_measures(shifts())
    assert out["hours"].sum() == pytest.approx(20.0)
    assert out["payroll_cents"].sum() == 29400


def test_missing_rate_is_flagged_not_estimated():
    out = rules.labor_shift_measures(shifts())
    assert out["missing_rate"].tolist() == [False, False, True]
    assert pd.isna(out["payroll_cents"].iloc[2])


@pytest.mark.parametrize(
    ("record_type", "status", "countable"),
    [
        ("EVENT", "Definite", True),
        ("EVENT", "Tentative", False),
        ("EVENT", "Lost", False),
        ("EVENT", "Canceled", False),
        ("LEAD", "Lead", False),
    ],
)
def test_only_definite_events_count(record_type, status, countable):
    assert rules.is_countable_event(record_type, status) is countable


def test_unknown_booking_status_fails_loudly():
    with pytest.raises(rules.UnmappedLabel):
        rules.is_countable_event("EVENT", "Confirmed")


def test_unknown_record_type_fails_loudly():
    with pytest.raises(rules.UnmappedLabel):
        rules.is_countable_event("EVNT", "Definite")


def test_missing_labor_department_fails_loudly():
    with pytest.raises(rules.UnmappedLabel):
        rules.labor_department(None)


def test_multi_day_booking_uses_event_money_on_each_event_date():
    df = pd.DataFrame(
        {
            "record_type": ["EVENT", "EVENT", "EVENT"],
            "booking_status": ["Definite", "Definite", "Tentative"],
            "booking_id": ["BK1", "BK1", "BK2"],
            "event_date": pd.to_datetime(["2026-09-26", "2026-09-27", "2026-09-27"]),
            "grand_total": [11128.0, 11128.0, 5000.0],
            "booking_grand_total": [22256.0, 22256.0, 5000.0],
        }
    )
    out = rules.private_event_revenue(df)
    assert out["event_date"].tolist() == [date(2026, 9, 26), date(2026, 9, 27)]
    assert out["revenue_cents"].sum() == 2225600
    assert out["booking_id"].nunique() == 1
