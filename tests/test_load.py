from datetime import date

import duckdb
import pandas as pd
import pytest

from pipeline import load, rules

TODAY = date(2026, 10, 5)


def sources():
    ticket = {
        "order_id": "O-1",
        "attraction_prefix": "SSD",
        "location_id": "L-1001",
        "merchant_id": 1,
        "package_id": "P-ADULT",
        "ticket_status": "CONFIRMED",
        "quantity": 2,
        "retail_amount": 72.0,
        "tax_amount": 0.0,
        "fee_amount": 0.0,
        "ticket_value": 70.0,
        "promotional_code": None,
        "event_date": pd.Timestamp("2026-10-03"),
        "event_time": pd.Timestamp("2026-10-03 16:00"),
        "date_sold": pd.Timestamp("2026-10-01"),
        "customer_country": "XX",
        "o_device": None,
        "source_system": "NT",
        "record_status": "ACTIVE",
    }
    tickets = pd.DataFrame(
        [
            {**ticket, "ticket_line_id": "SSD-T1", "ingestion_ts": "2026-10-04 06:00"},
            {**ticket, "ticket_line_id": "SSD-T1", "ingestion_ts": "2026-10-05 06:00"},
            {
                **ticket,
                "ticket_line_id": "SSD-T2",
                "ingestion_ts": "2026-10-05 06:00",
                "event_date": pd.Timestamp("2026-10-04"),
                "package_id": "P-PHOTO",
            },
        ]
    )
    packages = pd.DataFrame(
        {
            "attraction_prefix": ["SSD", "SSD"],
            "package_id": ["P-ADULT", "P-PHOTO"],
            "package_name": ["General Admission - Adult", "Souvenir Photo Package"],
            "package_class": ["INDIVIDUAL", "NON-ADMISSION"],
            "internal_name": ["adult", "photo"],
            "ticket_type": ["GENERAL ADMISSION", "ADD-ON"],
            "is_season_pass": [0, 0],
            "source_system": ["NT", "NT"],
        }
    )
    merchants = pd.DataFrame(
        {
            "merchant_id": [1],
            "merchant_name": ["Gate Terminal"],
            "sales_channel": ["Walk Up"],
        }
    )
    pos = pd.DataFrame(
        {
            "venue_code": ["SSD", "SSD", "SSD"],
            "outlet": ["Bar", "Cafe", "Cafe"],
            "order_id": ["SSD-O1", "SSD-O2", "SSD-O3"],
            "order_created_date": pd.to_datetime(
                ["2026-10-04 00:30", "2026-10-03 10:00", "2026-10-04 10:00"]
            ),
            "product_name": ["Beer", "Latte", "Latte"],
            "product_category": ["Alcohol", "Beverage", "Beverage"],
            "item_quantity": [1, 2, 1],
            "item_price": [8.0, 5.0, 5.0],
            "discount_amount": [0.0, 0.0, 0.0],
            "is_voided": ["N", "N", "N"],
            "voided_reason": [None, None, None],
            "tender_type": ["Card", "Card", "Cash"],
            "subtotal": [8.0, 10.0, 5.0],
            "tax": [0.66, 0.82, 0.41],
            "gratuity": [1.6, 0.0, 0.0],
            "final_total": [10.26, 10.82, 5.41],
        }
    )
    events = pd.DataFrame(
        {
            "record_type": ["EVENT", "LEAD"],
            "event_id": ["EV-1", None],
            "booking_id": ["BK-1", None],
            "lead_id": ["LD-1", "LD-2"],
            "venue_code": ["SSD", "SSD"],
            "location_name": ["Summit Sky Deck"] * 2,
            "booking_market_segment": ["Corporate", "Social"],
            "booking_status": ["Definite", "Lead"],
            "event_date": [pd.Timestamp("2026-10-02"), pd.NaT],
            "grand_total": [6565.0, None],
            "booking_grand_total": [6565.0, None],
            "lost_reason_name": [None, "free text"],
        }
    )
    labor = pd.DataFrame(
        {
            "venue_code": ["SSD", "SSD"],
            "paygroup_id": ["PG-DEN"] * 2,
            "person_id": ["E1", "E2"],
            "location_name": ["summit sky deck ", "Summit Sky Deck"],
            "working_dept": ["OPS", "Food & Beverage"],
            "position": ["Ticket Taker", "Server"],
            "date": pd.to_datetime(["2026-10-03", "2026-10-03"]),
            "actual_in": pd.to_datetime(["2026-10-03 09:00", "2026-10-03 22:00"]),
            "actual_out": pd.to_datetime(["2026-10-03 17:30", "2026-10-04 02:00"]),
            "rate": [18.0, None],
            "total_hrs": [8.0, 4.0],
            "total_earnings": [144.0, None],
            "tips": [0.0, 40.0],
            "comments": [None, "free text"],
        }
    )
    venues = pd.DataFrame(
        {
            "venue_code": ["SSD"],
            "venue_name": ["Summit Sky Deck"],
            "city": ["Denver"],
            "state": ["CO"],
            "latitude": [39.7],
            "longitude": [-105.0],
            "timezone": ["America/Denver"],
            "location_id": ["L-1001"],
            "attraction_prefix": ["SSD"],
        }
    )
    budget = pd.DataFrame(
        {
            "venue_code": ["SSD"],
            "date": [pd.Timestamp("2026-10-03")],
            "department": ["Ticket"],
            "budget_revenue": [9000.0],
            "budget_attendance": [250.0],
        }
    )
    return {
        "fact_ticket": tickets,
        "dim_package": packages,
        "dim_merchant": merchants,
        "pos_order_lines": pos,
        "private_events": events,
        "labor_actual": labor,
        "dim_venue": venues,
        "budget_daily": budget,
    }


def test_transform_applies_the_rules():
    tables, checks = load.transform(sources(), TODAY)
    assert checks.blocking_failures() == []
    tickets = tables["daily_tickets"]
    assert tickets["attendance"].sum() == 2
    assert tickets["ticket_revenue_cents"].sum() == 7000
    pos = tables["daily_pos"].set_index(["business_date", "outlet"])["revenue_cents"]
    # The 00:30 Bar sale belongs to business day 10-03, and Bar shows a real
    # zero on 10-04 because Cafe traded that day.
    assert pos[(date(2026, 10, 3), "Bar")] == 800
    assert pos[(date(2026, 10, 4), "Bar")] == 0
    labor = tables["daily_labor"].set_index("department")
    assert labor.loc["Restaurant", "missing_rate_shifts"] == 1
    assert labor.loc["Operations", "payroll_cents"] == 14400
    assert tables["daily_private_events"]["revenue_cents"].sum() == 656500


PII_AND_FREE_TEXT = {
    "order_id",
    "customer_country",
    "person_id",
    "comments",
    "notes",
    "voided_reason",
    "lost_reason_name",
}


def test_no_guest_data_or_free_text_reaches_the_database():
    tables, _ = load.transform(sources(), TODAY)
    for name, frame in tables.items():
        assert not PII_AND_FREE_TEXT & set(frame.columns), name


def test_subtotal_mismatch_blocks_the_load():
    src = sources()
    src["pos_order_lines"].loc[0, "subtotal"] = 9.0
    _, checks = load.transform(src, TODAY)
    assert [r["check_name"] for r in checks.blocking_failures()] == [
        "pos_order_subtotal_matches_lines"
    ]


def test_unmapped_label_stops_the_load():
    src = sources()
    src["labor_actual"].loc[0, "working_dept"] = "Valet"
    with pytest.raises(rules.UnmappedLabel, match="Valet"):
        load.transform(src, TODAY)


def test_missing_files_are_named(tmp_path):
    (tmp_path / "01_Ticketing.xlsx").touch()
    with pytest.raises(load.LoadError, match="02_POS_FandB_Merch.xlsx"):
        load.read_sources(tmp_path)


def test_two_loads_give_byte_identical_rollups(tmp_path):
    for run in ("a", "b"):
        tables, checks = load.transform(sources(), TODAY)
        db = tmp_path / f"{run}.duckdb"
        load.write(tables, checks, {"run_id": run}, db)
        load.export(db, tmp_path / run)
    for name in load.ROLLUPS:
        first = (tmp_path / "a" / f"{name}.csv").read_bytes()
        assert first == (tmp_path / "b" / f"{name}.csv").read_bytes(), name


def test_write_replaces_the_database_atomically(tmp_path):
    tables, checks = load.transform(sources(), TODAY)
    db = tmp_path / "attractions.duckdb"
    load.write(tables, checks, {"run_id": "x"}, db)
    assert not db.with_suffix(".tmp.duckdb").exists()
    con = duckdb.connect(str(db), read_only=True)
    assert con.execute("SELECT count(*) FROM user_venues").fetchone()[0] == 4
    con.close()
