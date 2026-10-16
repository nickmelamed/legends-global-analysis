import pytest

from pipeline import reconcile


@pytest.mark.parametrize(
    ("measure", "ours", "target", "status", "difference"),
    [
        ("ticket_revenue", 61575.71, 61576, "match", 0),
        ("ticket_revenue", 61575.50, 61576, "match", 0),
        ("ticket_revenue", 61575.49, 61576, "miss", -1),
        ("total_revenue", 56218.57, 56220, "miss", -1),
        ("attendance", 1849, 1849, "match", 0),
        ("attendance", 1848, 1849, "miss", -1),
        ("labor_hours", 484.47, 484.5, "match", 0),
        ("labor_hours", 484.44, 484.5, "miss", -0.1),
        ("labor_hours", 358.69, 358.7, "match", 0),
    ],
)
def test_compare_rounds_ours_to_the_target_precision(
    measure, ours, target, status, difference
):
    row = reconcile.compare(measure, ours, target)
    assert row["status"] == status
    assert row["difference"] == pytest.approx(difference)


def test_none_is_a_miss_not_zero():
    row = reconcile.compare("fnb_revenue", None, 9230)
    assert row["status"] == "no data"


def test_required_venue_miss_fails_the_run():
    rows = [
        {"venue": "SSD", "status": "match"},
        {"venue": "RTL", "status": "miss"},
    ]
    assert reconcile.required_misses(rows, ["SSD"]) == []
    rows[0]["status"] = "miss"
    assert reconcile.required_misses(rows, ["SSD"]) == [rows[0]]
