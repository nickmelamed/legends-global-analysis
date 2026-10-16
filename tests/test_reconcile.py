import duckdb
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


def test_week_hours_are_rounded_once():
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE daily_tickets AS SELECT 'SSD' AS venue_code, "
        "DATE '2026-09-28' AS business_date, 10 AS attendance, "
        "1000 AS ticket_revenue_cents"
    )
    con.execute(
        "CREATE TABLE daily_pos AS SELECT 'SSD' AS venue_code, "
        "DATE '2026-09-28' AS business_date, 'fnb' AS revenue_line, "
        "500 AS revenue_cents"
    )
    con.execute(
        "CREATE TABLE daily_private_events AS SELECT 'SSD' AS venue_code, "
        "DATE '2026-09-28' AS event_date, 0 AS revenue_cents"
    )
    # 484.449 must compare as 484.4, not 484.45 then 484.5.
    con.execute(
        "CREATE TABLE daily_labor AS SELECT 'SSD' AS venue_code, "
        "DATE '2026-09-28' AS work_date, 484.449::DOUBLE AS hours, "
        "100 AS payroll_cents, 0 AS missing_rate_shifts, "
        "0.0::DOUBLE AS missing_rate_hours"
    )
    ours = reconcile.week_actuals(con, "SSD", "2026-09-28", "2026-10-04")
    assert reconcile.compare("labor_hours", ours["labor_hours"], 484.5)["status"] == (
        "miss"
    )
