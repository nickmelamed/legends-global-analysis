"""The tools Ask the data gives the model, and the code that runs them.

Each tool resolves its window with ``api.windows`` and reads the same
``overview.build`` result the Overview page shows, so an answer and the page
cannot disagree. No tool takes a venue. The venues are the request's scope.
Outputs are built from an allowlist of fields, rounded the way the page shows
them, so the model copies figures and never has to compute one.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException

from api import overview
from api.queries import TicketFilter
from api.scope import Scope
from api.windows import Window, resolve

PERIODS = ["last_week", "month_to_date", "year_to_date", "custom"]
COMPARES = ["none", "prior_period", "last_year"]
WINDOW_FIELDS = (
    "start",
    "end",
    "days_total",
    "days_elapsed",
    "elapsed_end",
    "compare_mode",
    "comparison_start",
    "comparison_elapsed_end",
    "crosses_cutover",
)

_ARGS = {
    "type": "object",
    "properties": {
        "period": {"type": "string", "enum": PERIODS},
        "start": {
            "type": ["string", "null"],
            "description": "First day, YYYY-MM-DD. Only for period=custom.",
        },
        "end": {
            "type": ["string", "null"],
            "description": "Last day, YYYY-MM-DD. Only for period=custom.",
        },
        "compare": {"type": "string", "enum": COMPARES},
    },
    "required": ["period", "start", "end", "compare"],
    "additionalProperties": False,
}

TOOLS = [
    {
        "name": "resolve_window",
        "description": (
            "Return the dates a period covers: the current window, the days "
            "elapsed so far (up to yesterday) and the comparison window."
        ),
        "input_schema": _ARGS,
        "strict": True,
    },
    {
        "name": "get_kpis",
        "description": (
            "Return total revenue, per cap, attendance, ticket revenue, average "
            "ticket price, F&B, merchandise and private events revenue for the "
            "selected venues: actual, comparison, change, percent change and "
            "pace to plan."
        ),
        "input_schema": _ARGS,
        "strict": True,
    },
    {
        "name": "get_department_revenue",
        "description": (
            "Return revenue by department (Ticket, Restaurant, Cafe, "
            "Merchandise, Private Events) with comparison and pace to plan."
        ),
        "input_schema": _ARGS,
        "strict": True,
    },
    {
        "name": "get_labor",
        "description": (
            "Return payroll, labor hours, guests per labor hour and payroll as "
            "a percent of revenue, with comparison. Payroll is marked "
            "incomplete when some shifts have no pay rate."
        ),
        "input_schema": _ARGS,
        "strict": True,
    },
]

SECTIONS = {
    "get_kpis": ("kpis", "revenue_lines"),
    "get_department_revenue": ("departments",),
    "get_labor": ("labor",),
}


class ToolError(ValueError):
    """A tool call with arguments the tool cannot use."""


def _round(value):
    return round(value, 2) if isinstance(value, float) else value


def _window(args: dict, today: date) -> Window:
    period, compare = args.get("period"), args.get("compare")
    if period not in PERIODS or compare not in COMPARES:
        raise ToolError(f"period must be one of {PERIODS}, compare one of {COMPARES}")
    try:
        start = date.fromisoformat(args["start"]) if args.get("start") else None
        end = date.fromisoformat(args["end"]) if args.get("end") else None
        return resolve(
            period,
            start if period == "custom" else None,
            end if period == "custom" else None,
            compare != "none",
            "prior_period" if compare == "none" else compare,
            today,
        )
    except ValueError as e:
        raise ToolError("start and end must be YYYY-MM-DD") from e
    except HTTPException as e:
        raise ToolError(str(e.detail)) from e


def _window_out(window: Window) -> dict:
    full = window.as_dict()
    return {k: full[k] for k in WINDOW_FIELDS}


def _metric(m: dict) -> dict:
    current, comparison = m["current"], m["comparison"]
    out = {
        "metric": m["label"],
        "unit": m["unit"],
        "current": _round(current),
        "comparison": _round(comparison),
        "change": None
        if current is None or comparison is None
        else round(current - comparison, 2),
        "percent_change": _round(m["delta_pct"]),
        "current_has_no_data_days": m["data_gap"],
        "comparison_has_no_data_days": m["comparison_data_gap"],
    }
    if m["pace"]:
        out["plan"] = _round(m["pace"]["budget"])
        out["percent_of_plan"] = _round(m["pace"]["pct"])
        out["pace_status"] = m["pace"]["status"]
    if m.get("incomplete"):
        out["shifts_missing_pay_rate"] = m["incomplete"]["missing_rate_shifts"]
        out["hours_missing_pay_rate"] = m["incomplete"]["missing_rate_hours"]
    return out


def run(name: str, args: dict, scope: Scope, today: date) -> dict:
    """Run tool ``name`` for the request's scope and return its output."""
    window = _window(args, today)
    out = {"venues": list(scope.venues), "window": _window_out(window)}
    if name == "resolve_window":
        return out
    if name not in SECTIONS:
        raise ToolError(f"unknown tool {name}")
    built = overview.build(scope, window, TicketFilter())
    out["metrics"] = [_metric(m) for s in SECTIONS[name] for m in built[s]]
    out["no_data"] = [
        {"venue": g["venue"], "date": g["date"], "feed": g["feed"]}
        for g in built["data_gaps"]
    ]
    return out
