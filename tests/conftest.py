"""A tiny synthetic database for the API tests.

Two venues, 2026-09-21 to 2026-10-04. Every SSD day has 10 guests ($280 of
tickets: 8 Web at $30, 2 Group at $20), $110 of POS (Restaurant $50, Bar $10,
Cafe $20, Gift Shop $30), 10 labor hours and $200 payroll. SSD has a $500
private event on 2026-10-02 and a missing-rate shift on 2026-09-30. RTL is the
same for tickets and POS but has no rows on 2026-10-01, a missing feed.
"""

from datetime import date, timedelta

import duckdb
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.settings import Settings

FIRST = date(2026, 9, 21)
LAST = date(2026, 10, 4)
GAP = ("RTL", date(2026, 10, 1))
DAYS = [FIRST + timedelta(days=i) for i in range((LAST - FIRST).days + 1)]
VENUES = ["SSD", "RTL"]


def _tables() -> dict[str, pd.DataFrame]:
    tickets, pos, labor, coverage, budget = [], [], [], [], []
    for v in VENUES:
        for d in DAYS:
            missing = (v, d) == GAP
            for feed in ("tickets", "pos", "labor"):
                status = "no_data" if missing and feed != "labor" else "ok"
                coverage.append((v, d, feed, status))
            if not missing:
                tickets += [
                    (v, d, "INDIVIDUAL", "Web", 8, 24000, 8),
                    (v, d, "GROUP", "Group", 2, 4000, 2),
                ]
                pos += [
                    (v, d, "Restaurant", 5000, 3, "Restaurant", "fnb"),
                    (v, d, "Bar", 1000, 1, "Restaurant", "fnb"),
                    (v, d, "Cafe", 2000, 2, "Cafe", "fnb"),
                    (v, d, "Gift Shop", 3000, 1, "Merchandise", "merch"),
                ]
            short = v == "SSD" and d == date(2026, 9, 30)
            labor.append(
                (
                    v,
                    d,
                    "Operations",
                    10.0,
                    20000,
                    3,
                    1 if short else 0,
                    4.0 if short else 0.0,
                )
            )
            for dept, cents, guests in (
                ("Ticket", 30000, 10.0),
                ("Restaurant", 6000, None),
                ("Cafe", 2000, None),
                ("Merchandise", 3000, None),
                ("Private Events", 0, None),
            ):
                budget.append((v, d, dept, guests, cents))
    return {
        "dim_venue": pd.DataFrame(
            [("SSD", "Summit Sky Deck"), ("RTL", "Riverbend Tower Lookout")],
            columns=["venue_code", "venue_name"],
        ),
        "app_users": pd.DataFrame(
            [
                ("nick@dev", "Nick", "admin"),
                ("marcus@dev", "Marcus", "venue_manager"),
            ],
            columns=["email", "display_name", "role"],
        ),
        "user_venues": pd.DataFrame(
            [("nick@dev", "SSD"), ("nick@dev", "RTL"), ("marcus@dev", "SSD")],
            columns=["email", "venue_code"],
        ),
        "daily_tickets": pd.DataFrame(
            tickets,
            columns=[
                "venue_code",
                "business_date",
                "package_class",
                "sales_channel",
                "attendance",
                "ticket_revenue_cents",
                "lines",
            ],
        ),
        "daily_pos": pd.DataFrame(
            pos,
            columns=[
                "venue_code",
                "business_date",
                "outlet",
                "revenue_cents",
                "lines",
                "department",
                "revenue_line",
            ],
        ),
        "daily_labor": pd.DataFrame(
            labor,
            columns=[
                "venue_code",
                "work_date",
                "department",
                "hours",
                "payroll_cents",
                "shifts",
                "missing_rate_shifts",
                "missing_rate_hours",
            ],
        ),
        "daily_private_events": pd.DataFrame(
            [("SSD", date(2026, 10, 2), 50000, 1, 1)],
            columns=["venue_code", "event_date", "revenue_cents", "events", "bookings"],
        ),
        "budget_daily": pd.DataFrame(
            budget,
            columns=[
                "venue_code",
                "date",
                "department",
                "budget_attendance",
                "budget_revenue_cents",
            ],
        ),
        "feed_coverage": pd.DataFrame(
            coverage, columns=["venue_code", "business_date", "feed", "status"]
        ),
        "load_runs": pd.DataFrame(
            [("run-1", pd.Timestamp("2026-10-05 05:00"))],
            columns=["run_id", "finished_at"],
        ),
    }


@pytest.fixture(scope="session")
def api_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("api") / "api.duckdb"
    con = duckdb.connect(str(path))
    for name, frame in _tables().items():
        con.register("frame", frame)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM frame")
        con.unregister("frame")
    con.close()
    return path


@pytest.fixture
def make_client(api_db):
    def make(user: str | None = "nick@dev", today: date = date(2026, 10, 5)):
        app = create_app(Settings(db_path=api_db, today=today, dev_user=None))
        headers = {"X-Dev-User": user} if user else {}
        return TestClient(app, headers=headers)

    return make
