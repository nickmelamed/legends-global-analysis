"""Assemble the Overview: KPIs, labor, departments and pace to plan.

Ratios and statuses come from ``pipeline.rules``. This module only picks
which sums feed which measure.
"""

from __future__ import annotations

from datetime import date

from api.queries import FEEDS, Measures, TicketFilter, budget, measures
from api.scope import Scope
from api.windows import Window
from pipeline import rules

DEPARTMENTS = ["Ticket", "Restaurant", "Cafe", "Merchandise", "Private Events"]
DEPARTMENT_FEED = {
    "Ticket": "tickets",
    "Restaurant": "pos",
    "Cafe": "pos",
    "Merchandise": "pos",
    "Private Events": None,
}
# Metrics the package class and sales channel filters change (D-010).
TICKET_FILTERED = ["attendance", "ticket_revenue", "atp", "department:Ticket"]
COST_METRICS = {"payroll", "labor_hours", "payroll_pct"}


def _dollars(cents: float | None) -> float | None:
    return None if cents is None else round(cents / 100, 2)


def _add(*parts: int | None) -> int | None:
    return None if any(p is None for p in parts) else sum(parts)


def _total_cents(m: Measures) -> int | None:
    return _add(m.ticket_cents_all, m.fnb_cents, m.merch_cents, m.events_cents)


def values(m: Measures) -> dict[str, float | None]:
    """Return every Overview measure for one range, in display units."""
    total = _total_cents(m)
    per_cap = rules.ratio(total, m.attendance_all)
    atp = rules.ratio(m.ticket_cents, m.attendance)
    payroll_share = rules.ratio(m.payroll_cents, total)
    out = {
        "total_revenue": _dollars(total),
        "per_cap": _dollars(per_cap),
        "attendance": m.attendance,
        "ticket_revenue": _dollars(m.ticket_cents),
        "atp": _dollars(atp),
        "fnb_revenue": _dollars(m.fnb_cents),
        "merch_revenue": _dollars(m.merch_cents),
        "private_events_revenue": _dollars(m.events_cents),
        "payroll": _dollars(m.payroll_cents),
        "labor_hours": m.hours,
        "guests_per_labor_hour": rules.ratio(m.attendance_all, m.hours),
        "payroll_pct": None if payroll_share is None else payroll_share * 100,
    }
    for dept in DEPARTMENTS:
        out[f"department:{dept}"] = _dollars(m.department_cents[dept])
    return out


METRIC_FEEDS = {
    "total_revenue": ("tickets", "pos"),
    "per_cap": ("tickets", "pos"),
    "attendance": ("tickets",),
    "ticket_revenue": ("tickets",),
    "atp": ("tickets",),
    "fnb_revenue": ("pos",),
    "merch_revenue": ("pos",),
    "private_events_revenue": (),
    "payroll": ("labor",),
    "labor_hours": ("labor",),
    "guests_per_labor_hour": ("tickets", "labor"),
    "payroll_pct": ("tickets", "pos", "labor"),
} | {
    f"department:{d}": (DEPARTMENT_FEED[d],) if DEPARTMENT_FEED[d] else ()
    for d in DEPARTMENTS
}

LABELS = {
    "total_revenue": ("Total revenue", "usd"),
    "per_cap": ("Total per cap", "usd"),
    "attendance": ("Attendance", "count"),
    "ticket_revenue": ("Ticket revenue", "usd"),
    "atp": ("Average ticket price", "usd"),
    "fnb_revenue": ("F&B revenue", "usd"),
    "merch_revenue": ("Merchandise revenue", "usd"),
    "private_events_revenue": ("Private events revenue", "usd"),
    "payroll": ("Payroll", "usd"),
    "labor_hours": ("Labor hours", "hours"),
    "guests_per_labor_hour": ("Guests per labor hour", "ratio"),
    "payroll_pct": ("Payroll % of revenue", "pct"),
} | {f"department:{d}": (d, "usd") for d in DEPARTMENTS}


def _pace(actual: float | None, plan: float | None) -> dict | None:
    if plan is None:
        return None
    share = rules.ratio(actual, plan)
    pct = None if share is None else share * 100
    return {
        "actual": actual,
        "budget": plan,
        "pct": pct,
        "status": rules.pace_status(pct),
    }


def _plans(bud: dict[str, tuple[int, float]], tf: TicketFilter) -> dict:
    """Return the budget for each metric that has one, in display units.

    The budget has no package class or channel split, so a ticket filter
    leaves the ticket metrics with no plan.
    """
    if not bud:
        return {}
    revenue = sum(c for c, _ in bud.values())
    guests = bud.get("Ticket", (0, 0.0))[1]
    plans = {
        "total_revenue": _dollars(revenue),
        "per_cap": _dollars(rules.ratio(revenue, guests)),
        "attendance": guests or None,
        "ticket_revenue": _dollars(bud.get("Ticket", (0, 0))[0]),
    }
    for dept in DEPARTMENTS:
        plans[f"department:{dept}"] = _dollars(bud[dept][0]) if dept in bud else None
    if tf.active:
        for key in TICKET_FILTERED:
            plans[key] = None
    return plans


def _gap_rows(scope: Scope, start: date, end: date) -> list[dict]:
    rows = scope.query(
        "SELECT venue_code, business_date, feed FROM feed_coverage "
        "WHERE venue_code IN {venues} AND status = 'no_data' "
        "AND business_date BETWEEN $start AND $end ORDER BY 2, 1, 3",
        {"start": start, "end": end},
    ).fetchall()
    return [{"venue": v, "date": d.isoformat(), "feed": f} for v, d, f in rows]


def build(scope: Scope, window: Window, tf: TicketFilter) -> dict:
    """Return the Overview response for the scoped venues and window."""
    current = measures(scope, window.start, window.end, tf)
    cur = values(current)
    cmp: dict = {}
    if window.comparison_start:
        cmp = values(
            measures(scope, window.comparison_start, window.comparison_end, tf)
        )
    plans: dict = {}
    elapsed_vals: dict = {}
    gaps: dict[str, int] = dict.fromkeys(FEEDS, 0)
    gap_rows: list[dict] = []
    if window.elapsed_end:
        elapsed = (
            current
            if window.elapsed_end == window.end
            else measures(scope, window.start, window.elapsed_end, tf)
        )
        elapsed_vals = values(elapsed)
        gaps = elapsed.feed_gaps
        plans = _plans(budget(scope, window.start, window.elapsed_end), tf)
        gap_rows = _gap_rows(scope, window.start, window.elapsed_end)

    def metric(key: str) -> dict:
        label, unit = LABELS[key]
        out = {
            "key": key,
            "label": label,
            "unit": unit,
            "current": cur[key],
            "comparison": cmp.get(key),
            "delta_pct": rules.pct_change(cur[key], cmp.get(key)),
            "cost": key in COST_METRICS,
            "ticket_filtered": tf.active and key in TICKET_FILTERED,
            "data_gap": any(gaps[f] for f in METRIC_FEEDS[key]),
            "pace": _pace(elapsed_vals.get(key), plans.get(key)),
        }
        if key in ("payroll", "payroll_pct"):
            out["incomplete"] = (
                {
                    "missing_rate_shifts": current.missing_rate_shifts,
                    "missing_rate_hours": round(current.missing_rate_hours, 2),
                }
                if current.missing_rate_shifts
                else None
            )
        return out

    return {
        "venues": list(scope.venues),
        "window": window.as_dict(),
        "filters": {
            "package_class": list(tf.package_classes),
            "sales_channel": list(tf.sales_channels),
            "ticket_filter_applies_to": TICKET_FILTERED,
        },
        "kpis": [
            metric(k)
            for k in ("total_revenue", "per_cap", "attendance", "ticket_revenue")
        ],
        "labor": [
            metric(k)
            for k in ("payroll", "labor_hours", "guests_per_labor_hour", "payroll_pct")
        ],
        "departments": [metric(f"department:{d}") for d in DEPARTMENTS],
        "revenue_lines": [
            metric(k)
            for k in ("atp", "fnb_revenue", "merch_revenue", "private_events_revenue")
        ],
        "data_gaps": gap_rows,
        "feed_gap_days": gaps,
    }
