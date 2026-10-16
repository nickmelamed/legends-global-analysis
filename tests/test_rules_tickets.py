import pandas as pd
import pytest

from pipeline import rules


def ticket(**overrides):
    row = {
        "ticket_line_id": "SSD-T1",
        "source_system": "NT",
        "ticket_status": "CONFIRMED",
        "package_class": "INDIVIDUAL",
        "quantity": 2,
        "ticket_value": 70.0,
        "ingestion_ts": pd.Timestamp("2026-06-08 06:00"),
    }
    row.update(overrides)
    return row


def test_dedup_keeps_latest_load_and_counts_drops():
    df = pd.DataFrame(
        [
            ticket(ingestion_ts=pd.Timestamp("2026-06-09 06:00"), quantity=3),
            ticket(ingestion_ts=pd.Timestamp("2026-06-08 06:00"), quantity=2),
            ticket(ticket_line_id="SSD-T2"),
        ]
    )
    out, dropped = rules.dedup_ticket_loads(df)
    assert dropped == 1
    assert sorted(out["ticket_line_id"]) == ["SSD-T1", "SSD-T2"]
    assert out.loc[out["ticket_line_id"] == "SSD-T1", "quantity"].item() == 3


def test_dedup_leaves_unique_lines_alone():
    df = pd.DataFrame([ticket(), ticket(ticket_line_id="SSD-T2")])
    out, dropped = rules.dedup_ticket_loads(df)
    assert dropped == 0
    assert len(out) == 2


@pytest.mark.parametrize(
    ("source", "status", "cancelled"),
    [
        ("LT", "Cancelled", True),
        ("LT", "In Process", False),
        ("LT", "Redeemed", False),
        ("LT", "No Show", False),
        ("NT", "CANCELLED", True),
        ("NT", "CONFIRMED", False),
        ("NT", "REDEEMED", False),
        ("NT", "NO_SHOW", False),
        ("NT", "PART_REDEEMED", False),
    ],
)
def test_cancelled_status_per_source(source, status, cancelled):
    assert rules.is_cancelled(source, status) is cancelled


@pytest.mark.parametrize(
    ("source", "status"),
    [("LT", "CANCELLED"), ("NT", "Cancelled"), ("NT", "VOID"), ("XX", "Cancelled")],
)
def test_status_from_the_other_vocabulary_fails_loudly(source, status):
    with pytest.raises(rules.UnmappedLabel):
        rules.is_cancelled(source, status)


@pytest.mark.parametrize(
    ("package_class", "countable"),
    [
        ("INDIVIDUAL", True),
        ("GROUP", True),
        ("FIT", True),
        ("PROMOTION", True),
        ("NON-ADMISSION", False),
        ("EVENT", False),
    ],
)
def test_package_class_decides_admission(package_class, countable):
    assert rules.is_countable_ticket("NT", "CONFIRMED", package_class) is countable


def test_cancelled_admission_is_not_countable():
    assert rules.is_countable_ticket("LT", "Cancelled", "INDIVIDUAL") is False


def test_zero_value_pass_visit_and_no_show_count():
    df = pd.DataFrame(
        [
            ticket(ticket_status="NO_SHOW"),
            ticket(ticket_line_id="SSD-T2", ticket_value=0.0, quantity=1),
            ticket(ticket_line_id="SSD-T3", package_class="NON-ADMISSION"),
            ticket(ticket_line_id="SSD-T4", package_class="EVENT", ticket_value=0.0),
            ticket(ticket_line_id="SSD-T5", ticket_status="CANCELLED"),
        ]
    )
    mask = rules.countable_ticket_mask(df)
    assert mask.tolist() == [True, True, False, False, False]
    assert df.loc[mask, "quantity"].sum() == 3


def test_unknown_package_class_fails_loudly():
    with pytest.raises(rules.UnmappedLabel):
        rules.is_countable_ticket("NT", "CONFIRMED", "BUNDLE")
