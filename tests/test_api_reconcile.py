"""The API's numbers for the reconciliation week against the Power BI targets.

Needs build/attractions.duckdb from ``make load``.
"""

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.settings import Settings
from pipeline import reconcile

DB = Path("build/attractions.duckdb")
TARGETS = json.loads(Path("tests/fixtures/pbi_targets.json").read_text())


@pytest.mark.slow
@pytest.mark.skipif(not DB.exists(), reason="run make load first")
@pytest.mark.parametrize("venue", TARGETS["required"])
def test_overview_matches_power_bi_for_the_week(venue):
    app = create_app(Settings(db_path=DB, today=date(2026, 10, 5), dev_user=None))
    client = TestClient(app, headers={"X-Dev-User": "nick@dev"})
    window = TARGETS["window"]
    body = client.get(
        "/api/overview",
        params={"venue": venue, "start": window["start"], "end": window["end"]},
    ).json()
    ours = {
        m["key"]: m["current"]
        for section in ("kpis", "labor", "revenue_lines")
        for m in body[section]
    }
    rows = [
        reconcile.compare(measure, ours[measure], TARGETS["venues"][venue][measure])
        for measure in reconcile.MEASURES
    ]
    assert [r for r in rows if r["status"] != "match"] == []
