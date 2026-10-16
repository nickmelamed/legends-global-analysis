"""Overview, trend, freshness and export on the synthetic database.

Expected values are worked by hand from tests/conftest.py. Last Week with
today 2026-10-05 is 2026-09-28 to 2026-10-04, the prior period 2026-09-21 to
2026-09-27.
"""

from datetime import date

import pytest


def _metrics(body):
    return {
        m["key"]: m
        for section in ("kpis", "labor", "departments", "revenue_lines")
        for m in body[section]
    }


@pytest.fixture
def ssd_week(make_client):
    return make_client().get("/api/overview").json()


def test_default_is_summit_last_week_with_prior_period(ssd_week):
    w = ssd_week["window"]
    assert ssd_week["venues"] == ["SSD"]
    assert (w["start"], w["end"], w["days_total"], w["days_elapsed"]) == (
        "2026-09-28",
        "2026-10-04",
        7,
        7,
    )
    assert (w["comparison_start"], w["comparison_end"]) == ("2026-09-21", "2026-09-27")
    assert w["compare_mode"] == "prior_period"


def test_kpis_current_and_comparison(ssd_week):
    m = _metrics(ssd_week)
    # 7 x (280 + 110) + 500 private event = 3,230. Prior week has no event.
    assert m["total_revenue"]["current"] == 3230.0
    assert m["total_revenue"]["comparison"] == 2730.0
    assert m["total_revenue"]["delta_pct"] == pytest.approx(500 / 2730 * 100)
    assert m["attendance"]["current"] == 70
    assert m["ticket_revenue"]["current"] == 1960.0
    assert m["per_cap"]["current"] == pytest.approx(46.14)
    assert m["atp"]["current"] == 28.0
    assert m["fnb_revenue"]["current"] == 560.0
    assert m["merch_revenue"]["current"] == 210.0
    assert m["private_events_revenue"]["current"] == 500.0


def test_departments_put_bar_in_restaurant(ssd_week):
    m = _metrics(ssd_week)
    assert [d["label"] for d in ssd_week["departments"]] == [
        "Ticket",
        "Restaurant",
        "Cafe",
        "Merchandise",
        "Private Events",
    ]
    assert m["department:Restaurant"]["current"] == 420.0
    assert m["department:Cafe"]["current"] == 140.0


def test_pace_to_plan(ssd_week):
    m = _metrics(ssd_week)
    # Budget 7 x (300 + 60 + 20 + 30) = 2,870 and 70 guests.
    total = m["total_revenue"]["pace"]
    assert total["budget"] == 2870.0
    assert total["pct"] == pytest.approx(3230 / 2870 * 100)
    assert total["status"] == "green"
    assert m["attendance"]["pace"]["status"] == "green"
    ticket = m["ticket_revenue"]["pace"]
    assert ticket["pct"] == pytest.approx(1960 / 2100 * 100)
    assert ticket["status"] == "amber"
    assert m["department:Restaurant"]["pace"]["pct"] == pytest.approx(100)
    assert m["labor_hours"]["pace"] is None


def test_labor_and_incomplete_payroll(ssd_week):
    m = _metrics(ssd_week)
    assert m["labor_hours"]["current"] == 70.0
    assert m["payroll"]["current"] == 1400.0
    assert m["payroll"]["cost"] is True
    assert m["payroll"]["incomplete"] == {
        "missing_rate_shifts": 1,
        "missing_rate_hours": 4.0,
    }
    assert m["payroll_pct"]["incomplete"] is not None
    assert m["guests_per_labor_hour"]["current"] == pytest.approx(1.0)
    assert m["payroll_pct"]["current"] == pytest.approx(1400 / 3230 * 100)


def test_ticket_filter_changes_ticket_metrics_only(make_client):
    body = make_client().get("/api/overview", params={"sales_channel": "Web"}).json()
    m = _metrics(body)
    assert m["attendance"]["current"] == 56
    assert m["ticket_revenue"]["current"] == 1680.0
    assert m["attendance"]["ticket_filtered"] is True
    assert m["attendance"]["pace"] is None
    assert m["total_revenue"]["current"] == 3230.0
    assert m["total_revenue"]["ticket_filtered"] is False
    assert m["per_cap"]["current"] == pytest.approx(46.14)
    assert "attendance" in body["filters"]["ticket_filter_applies_to"]


def test_unknown_filter_value_is_rejected(make_client):
    r = make_client().get("/api/overview", params={"sales_channel": "Carrier pigeon"})
    assert r.status_code == 422


def test_missing_feed_day_is_flagged_not_zero(make_client):
    body = make_client().get("/api/overview", params={"venue": "RTL"}).json()
    m = _metrics(body)
    assert m["attendance"]["current"] == 60
    assert m["attendance"]["data_gap"] is True
    assert m["labor_hours"]["data_gap"] is False
    assert {(g["date"], g["feed"]) for g in body["data_gaps"]} == {
        ("2026-10-01", "pos"),
        ("2026-10-01", "tickets"),
    }


def test_window_with_only_missing_days_is_no_data(make_client):
    body = (
        make_client()
        .get(
            "/api/overview",
            params={"venue": "RTL", "start": "2026-10-01", "end": "2026-10-01"},
        )
        .json()
    )
    m = _metrics(body)
    for key in ("attendance", "ticket_revenue", "total_revenue", "per_cap"):
        assert m[key]["current"] is None
    assert m["labor_hours"]["current"] == 10.0


def test_compare_off_and_last_year(make_client):
    c = make_client()
    off = c.get("/api/overview", params={"compare": "false"}).json()
    assert off["window"]["comparison_start"] is None
    assert _metrics(off)["total_revenue"]["delta_pct"] is None
    ly = c.get("/api/overview", params={"compare_mode": "last_year"}).json()["window"]
    assert (ly["comparison_start"], ly["comparison_end"]) == (
        "2025-09-29",
        "2025-10-05",
    )
    # No data that far back: comparison is None, not 0.
    body = c.get("/api/overview", params={"compare_mode": "last_year"}).json()
    assert _metrics(body)["attendance"]["comparison"] is None


def test_custom_range_must_be_ordered(make_client):
    r = make_client().get(
        "/api/overview", params={"start": "2026-10-04", "end": "2026-09-28"}
    )
    assert r.status_code == 422


def test_month_to_date_pace_uses_elapsed_days(make_client):
    body = make_client().get("/api/overview", params={"preset": "month_to_date"}).json()
    w = body["window"]
    assert (w["start"], w["end"], w["days_total"], w["days_elapsed"]) == (
        "2026-10-01",
        "2026-10-04",
        31,
        4,
    )


def test_future_days_in_a_custom_window_are_not_gaps(make_client):
    client = make_client(today=date(2026, 10, 3))
    body = client.get(
        "/api/overview", params={"start": "2026-09-28", "end": "2026-10-04"}
    ).json()
    m = _metrics(body)
    assert body["window"]["days_elapsed"] == 5
    assert m["total_revenue"]["data_gap"] is False
    # Pace over 2026-09-28 to 2026-10-02: 5 x 390 + 500 against 5 x 410.
    assert m["total_revenue"]["pace"]["pct"] == pytest.approx(2450 / 2050 * 100)


def test_trend_by_day_shows_no_data_as_none(make_client):
    body = make_client().get("/api/trend", params={"venue": "RTL"}).json()
    by_day = {p["bucket_start"]: p for p in body["current"]}
    assert by_day["2026-10-01"]["revenue"] is None
    assert by_day["2026-10-01"]["data_gap"] is True
    assert by_day["2026-09-30"]["revenue"] == 390.0
    assert by_day["2026-09-30"]["per_cap"] == 39.0
    assert len(body["comparison"]) == 7


def test_trend_week_bucket_flags_a_gap(make_client):
    body = (
        make_client().get("/api/trend", params={"venue": "RTL", "grain": "week"}).json()
    )
    [week] = body["current"]
    assert week["revenue"] == 6 * 390.0
    assert (week["data_gap"], week["no_data_days"]) == (True, 1)
    assert body["ticket_filters_apply"] is False


def test_freshness(make_client):
    assert make_client().get("/api/freshness").json()["stale"] is False
    stale = make_client(today=date(2026, 10, 9)).get("/api/freshness").json()
    assert stale["stale"] is True
    assert stale["stale_feeds"] == ["labor", "pos", "tickets"]


def test_export_carries_filters_and_time(make_client):
    r = make_client().get(
        "/api/export.csv", params={"package_class": "GROUP", "compare": "false"}
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = r.text.splitlines()
    assert lines[0] == "# Attractions Overview export"
    assert any(line.startswith("# exported_at: ") for line in lines)
    assert "# window: 2026-09-28 to 2026-10-04" in lines
    assert "# comparison: off" in lines
    assert "# package_class: GROUP" in lines
    assert "kpis,Attendance,count,14,no data,no data,no data,False,False" in lines
