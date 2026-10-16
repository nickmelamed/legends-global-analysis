"""FastAPI app. Run with ``uvicorn api.main:app``.

Every route takes a ``Scope`` from ``get_scope``, so none can read venue data
without the scope helper.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Annotated

import duckdb
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api import ask, overview, trend
from api.auth import load_user, signed_in_email
from api.llm import AnthropicClient, LLMClient, RecordedClient
from api.queries import FEEDS, TicketFilter
from api.scope import Scope, scoped_venues
from api.settings import Settings
from api.windows import CompareMode, Preset, Window, resolve
from pipeline import rules


def get_con(request: Request) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open the database read-only for one request."""
    con = duckdb.connect(str(request.app.state.settings.db_path), read_only=True)
    try:
        yield con
    finally:
        con.close()


def get_scope(
    request: Request,
    con: Annotated[duckdb.DuckDBPyConnection, Depends(get_con)],
    venue: Annotated[list[str] | None, Query()] = None,
) -> Scope:
    """Return the signed-in user's scope for the venues this request asks for."""
    user = load_user(con, signed_in_email(request))
    return Scope(user=user, venues=scoped_venues(user, venue), con=con)


def get_window(
    request: Request,
    preset: Preset | None = None,
    start: date | None = None,
    end: date | None = None,
    compare: bool = True,
    compare_mode: CompareMode = "prior_period",
) -> Window:
    """Resolve the date filters. A start and end with no preset is custom."""
    if preset is None:
        preset = "custom" if start or end else "last_week"
    elif preset != "custom" and (start or end):
        raise HTTPException(422, "start and end need preset=custom")
    today = request.app.state.settings.today
    return resolve(preset, start, end, compare, compare_mode, today)


def get_ticket_filter(
    scope: Annotated[Scope, Depends(get_scope)],
    package_class: Annotated[list[str] | None, Query()] = None,
    sales_channel: Annotated[list[str] | None, Query()] = None,
) -> TicketFilter:
    """Return the ticket filters, rejecting values the data does not have."""
    tf = TicketFilter(tuple(package_class or ()), tuple(sales_channel or ()))
    if tf.active:
        known = _filter_values(scope)
        if set(tf.package_classes) - set(known["package_classes"]) or set(
            tf.sales_channels
        ) - set(known["sales_channels"]):
            raise HTTPException(422, "unknown package class or sales channel")
    return tf


def _filter_values(scope: Scope) -> dict:
    rows = scope.query(
        "SELECT DISTINCT package_class, sales_channel FROM daily_tickets "
        "WHERE venue_code IN {venues}"
    ).fetchall()
    return {
        "package_classes": sorted({p for p, _ in rows}),
        "sales_channels": sorted({c for _, c in rows}),
    }


ScopeDep = Annotated[Scope, Depends(get_scope)]
WindowDep = Annotated[Window, Depends(get_window)]
FilterDep = Annotated[TicketFilter, Depends(get_ticket_filter)]


class AskBody(BaseModel):
    """A question for Ask the data."""

    question: str = Field(min_length=1, max_length=500)


def make_llm(settings: Settings) -> LLMClient:
    """Return the model client ``ASK_CLIENT`` names. Recorded is the default."""
    if settings.ask_client == "anthropic":
        return AnthropicClient(settings.ask_model)
    return RecordedClient(settings.recordings_dir)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app from ``settings``, or from the environment if None."""
    app = FastAPI(title="Attractions API")
    app.state.settings = settings or Settings.from_env()
    app.state.llm = make_llm(app.state.settings)

    @app.get("/api/filters")
    def filters(scope: ScopeDep) -> dict:
        """Return the user's venues and the ticket filter values."""
        names = dict(
            scope.con.execute("SELECT venue_code, venue_name FROM dim_venue").fetchall()
        )
        return {
            "user": {
                "email": scope.user.email,
                "display_name": scope.user.display_name,
                "role": scope.user.role,
            },
            "venues": [{"code": v, "name": names.get(v, v)} for v in scope.user.venues],
            "selected_venues": list(scope.venues),
            **_filter_values(scope),
            "presets": ["last_week", "month_to_date", "year_to_date", "custom"],
            "compare_modes": ["prior_period", "last_year"],
            "app_today": app.state.settings.today.isoformat(),
        }

    @app.get("/api/overview")
    def get_overview(scope: ScopeDep, window: WindowDep, tf: FilterDep) -> dict:
        """Return the Overview KPIs, labor, departments and pace."""
        return overview.build(scope, window, tf)

    @app.get("/api/trend")
    def get_trend(
        scope: ScopeDep, window: WindowDep, grain: trend.Grain = "day"
    ) -> dict:
        """Return the revenue trend and its comparison."""
        return trend.build(scope, window, grain)

    @app.post("/api/ask")
    def ask_data(scope: ScopeDep, body: AskBody) -> dict:
        """Answer a question with figures checked against the tool outputs."""
        names = dict(
            scope.con.execute("SELECT venue_code, venue_name FROM dim_venue").fetchall()
        )
        today = app.state.settings.today
        return ask.answer(body.question, scope, today, app.state.llm, names)

    @app.get("/api/freshness")
    def freshness(scope: ScopeDep) -> dict:
        """Return when the data last loaded and whether it is stale."""
        today = app.state.settings.today
        run = scope.con.execute(
            "SELECT run_id, finished_at FROM load_runs ORDER BY finished_at DESC"
        ).fetchone()
        rows = scope.query(
            "SELECT venue_code, feed, max(business_date) FROM feed_coverage "
            "WHERE venue_code IN {venues} AND status = 'ok' GROUP BY ALL"
        ).fetchall()
        latest = {v: {} for v in scope.venues}
        for venue, feed, day in rows:
            latest[venue][feed] = day
        # Each venue and feed is checked on its own, so one current venue
        # cannot hide a stale one.
        expected = rules.last_complete_day(today)
        stale_feeds = [
            {"venue": v, "feed": f}
            for v in scope.venues
            for f in FEEDS
            if (latest[v].get(f) or date.min) < expected
        ]
        return {
            "venues": list(scope.venues),
            "app_today": today.isoformat(),
            "last_load_run": run[0] if run else None,
            "last_load_finished_at": run[1].isoformat() if run else None,
            "latest_day": {
                v: {f: d.isoformat() for f, d in feeds.items()}
                for v, feeds in latest.items()
            },
            "expected_latest_day": expected.isoformat(),
            "stale": bool(stale_feeds) or run is None,
            "stale_feeds": stale_feeds,
        }

    @app.get("/api/export.csv")
    def export_csv(scope: ScopeDep, window: WindowDep, tf: FilterDep) -> Response:
        """Return the Overview as CSV, with the filters and export time on top."""
        data = overview.build(scope, window, tf)
        buf = io.StringIO()
        w = window.as_dict()
        comparison = "off"
        if w["comparison_start"]:
            comparison = (
                f"{w['comparison_start']} to {w['comparison_end']} "
                f"({w['compare_mode']})"
            )
            if w["comparison_elapsed_end"] is None:
                comparison += ", nothing elapsed to compare"
            elif w["comparison_elapsed_end"] != w["comparison_end"]:
                comparison += f", compared through {w['comparison_elapsed_end']}"
        elapsed = f"{w['days_elapsed']} of {w['days_total']} elapsed"
        if w["elapsed_end"]:
            elapsed += f", through {w['elapsed_end']}"
        for line in (
            "Attractions Overview export",
            f"exported_at: {datetime.now(UTC).isoformat(timespec='seconds')}",
            f"app_today: {app.state.settings.today.isoformat()}",
            f"user: {scope.user.email}",
            f"venues: {', '.join(scope.venues)}",
            f"window: {w['start']} to {w['end']}",
            f"days: {elapsed}",
            f"comparison: {comparison}",
            f"crosses_cutover: {str(w['crosses_cutover']).lower()}",
            f"package_class: {', '.join(tf.package_classes) or 'all'}",
            f"sales_channel: {', '.join(tf.sales_channels) or 'all'}",
            "ticket filters apply to: " + ", ".join(overview.TICKET_FILTERED),
        ):
            buf.write(f"# {line}\n")
        out = csv.writer(buf, lineterminator="\n")
        out.writerow(
            [
                "section",
                "metric",
                "unit",
                "current",
                "comparison",
                "delta_pct",
                "pace_pct",
                "data_gap",
                "comparison_data_gap",
                "incomplete",
            ]
        )
        for section in ("kpis", "labor", "departments", "revenue_lines"):
            for m in data[section]:
                out.writerow(
                    [
                        section,
                        m["label"],
                        m["unit"],
                        _cell(m["current"]),
                        _cell(m["comparison"]),
                        _cell(m["delta_pct"]),
                        "no plan" if m["pace"] is None else _cell(m["pace"]["pct"]),
                        m["data_gap"],
                        m["comparison_data_gap"],
                        bool(m.get("incomplete")),
                    ]
                )
        filename = f"attractions-overview-{w['start']}-{w['end']}.csv"
        return Response(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


def _cell(value: float | None) -> str:
    """Return a CSV cell. No data is written as "no data", never 0."""
    if value is None:
        return "no data"
    return f"{value:.2f}" if isinstance(value, float) else str(value)


app = create_app()
