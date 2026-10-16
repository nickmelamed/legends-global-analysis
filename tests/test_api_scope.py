"""Venue scope on every route. New /api routes are picked up automatically."""

import pytest
from fastapi.routing import APIRoute

from api.main import create_app
from api.settings import Settings

ROUTES = sorted(
    r.path
    for r in create_app(Settings(db_path=None, today=None, dev_user=None)).routes
    if isinstance(r, APIRoute) and r.path.startswith("/api")
)


def test_every_api_route_is_listed():
    assert {
        "/api/filters",
        "/api/overview",
        "/api/trend",
        "/api/freshness",
        "/api/export.csv",
    } <= set(ROUTES)


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize(
    "venues", [["RTL"], ["SSD", "RTL"], ["XXX"]], ids=["other", "mixed", "unknown"]
)
def test_restricted_user_gets_403_outside_scope(make_client, path, venues):
    r = make_client("marcus@dev").get(path, params={"venue": venues})
    assert r.status_code == 403


@pytest.mark.parametrize("path", ROUTES)
def test_restricted_user_default_is_their_venue_only(make_client, path):
    r = make_client("marcus@dev").get(path)
    assert r.status_code == 200
    if path.endswith(".csv"):
        assert "# venues: SSD\n" in r.text
        assert "RTL" not in r.text
    else:
        body = r.json()
        venues = body.get("selected_venues", body.get("venues"))
        assert venues == ["SSD"]
        assert "RTL" not in r.text


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("user", [None, "eve@dev"], ids=["none", "unknown"])
def test_unknown_user_gets_401(make_client, path, user):
    assert make_client(user).get(path).status_code == 401


def test_admin_can_read_another_venue(make_client):
    r = make_client("nick@dev").get("/api/overview", params={"venue": "RTL"})
    assert r.status_code == 200
    assert r.json()["venues"] == ["RTL"]


def test_filters_list_only_the_users_venues(make_client):
    body = make_client("marcus@dev").get("/api/filters").json()
    assert [v["code"] for v in body["venues"]] == ["SSD"]
