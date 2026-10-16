"""SQL over the daily rollups. Every query runs through ``Scope.query``.

Money is summed in cents and converted to dollars only when a measure leaves
this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from api.scope import Scope

FEEDS = ("tickets", "pos", "labor")
# Private events have no feed of their own. A day counts as loaded for them
# when any feed covers the venue that day, so dates before the data starts or
# after yesterday are no data rather than $0.
EVENTS = "events"


@dataclass(frozen=True)
class TicketFilter:
    """Package class and channel filters, applied to ticket metrics only (D-010)."""

    package_classes: tuple[str, ...] = ()
    sales_channels: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        """Return whether any ticket filter is set."""
        return bool(self.package_classes or self.sales_channels)

    def sql(self) -> tuple[str, dict]:
        """Return an AND clause and its bound parameters."""
        clause, params = "", {}
        for column, values, prefix in (
            ("package_class", self.package_classes, "_pc"),
            ("sales_channel", self.sales_channels, "_sc"),
        ):
            if values:
                names = {f"{prefix}{i}": v for i, v in enumerate(values)}
                clause += f" AND {column} IN (" + ", ".join(f"${k}" for k in names)
                clause += ")"
                params |= names
        return clause, params


@dataclass
class Measures:
    """Raw sums for one date range over the scoped venues. Cents are ints."""

    attendance_all: int | None = None
    ticket_cents_all: int | None = None
    attendance: int | None = None
    ticket_cents: int | None = None
    department_cents: dict[str, int | None] = field(default_factory=dict)
    fnb_cents: int | None = None
    merch_cents: int | None = None
    events_cents: int | None = None
    hours: float | None = None
    payroll_cents: int | None = None
    missing_rate_shifts: int = 0
    missing_rate_hours: float = 0.0
    feed_gaps: dict[str, int] = field(default_factory=dict)
    feed_days: dict[str, int] = field(default_factory=dict)


MEASURES_SQL = """
WITH t AS (
    SELECT sum(attendance) AS att_all, sum(ticket_revenue_cents) AS tix_all,
           sum(attendance) FILTER (WHERE true {ticket_filter}) AS att,
           sum(ticket_revenue_cents) FILTER (WHERE true {ticket_filter}) AS tix
    FROM daily_tickets
    WHERE venue_code IN {venues} AND business_date BETWEEN $start AND $end
), p AS (
    SELECT sum(revenue_cents) FILTER (WHERE revenue_line = 'fnb') AS fnb,
           sum(revenue_cents) FILTER (WHERE revenue_line = 'merch') AS merch,
           sum(revenue_cents) FILTER (WHERE department = 'Restaurant') AS restaurant,
           sum(revenue_cents) FILTER (WHERE department = 'Cafe') AS cafe,
           sum(revenue_cents) FILTER (WHERE department = 'Merchandise') AS merchandise
    FROM daily_pos
    WHERE venue_code IN {venues} AND business_date BETWEEN $start AND $end
), e AS (
    SELECT coalesce(sum(revenue_cents), 0) AS events
    FROM daily_private_events
    WHERE venue_code IN {venues} AND event_date BETWEEN $start AND $end
), l AS (
    SELECT sum(hours) AS hours, sum(payroll_cents) AS payroll,
           coalesce(sum(missing_rate_shifts), 0) AS missing_shifts,
           coalesce(sum(missing_rate_hours), 0) AS missing_hours
    FROM daily_labor
    WHERE venue_code IN {venues} AND work_date BETWEEN $start AND $end
)
SELECT * FROM t, p, e, l
"""

COVERAGE_SQL = """
SELECT feed, count(*) FILTER (WHERE status = 'ok') AS ok_days
FROM feed_coverage
WHERE venue_code IN {venues} AND business_date BETWEEN $start AND $end
GROUP BY feed
UNION ALL
SELECT 'events', count(DISTINCT (venue_code, business_date))
FROM feed_coverage
WHERE venue_code IN {venues} AND business_date BETWEEN $start AND $end
"""


def measures(scope: Scope, start: date, end: date, tf: TicketFilter) -> Measures:
    """Return the raw sums for ``start`` to ``end``.

    A feed with no ok day in the range gives None for its measures, never 0.
    Days a feed should have covered but did not are counted in ``feed_gaps``.
    """
    clause, fparams = tf.sql()
    params = {"start": start, "end": end, **fparams}
    rel = scope.query(MEASURES_SQL.replace("{ticket_filter}", clause), params)
    row = dict(zip([c[0] for c in rel.description], rel.fetchone(), strict=True))
    ok = dict(scope.query(COVERAGE_SQL, {"start": start, "end": end}).fetchall())
    expected = ((end - start).days + 1) * len(scope.venues)
    m = Measures()
    m.feed_days = {f: int(ok.get(f, 0)) for f in (*FEEDS, EVENTS)}
    m.feed_gaps = {f: expected - n for f, n in m.feed_days.items()}

    def val(name: str, feed: str, cast=int):
        if m.feed_days[feed] == 0:
            return None
        return cast(row[name] or 0)

    m.attendance_all = val("att_all", "tickets")
    m.ticket_cents_all = val("tix_all", "tickets")
    m.attendance = val("att", "tickets")
    m.ticket_cents = val("tix", "tickets")
    m.fnb_cents = val("fnb", "pos")
    m.merch_cents = val("merch", "pos")
    m.events_cents = val("events", EVENTS)
    m.department_cents = {
        "Ticket": m.ticket_cents,
        "Restaurant": val("restaurant", "pos"),
        "Cafe": val("cafe", "pos"),
        "Merchandise": val("merchandise", "pos"),
        "Private Events": m.events_cents,
    }
    m.hours = val("hours", "labor", float)
    # Payroll stays None when no shift in the range has a rate (D-006).
    payroll = row["payroll"]
    m.payroll_cents = None if payroll is None else int(payroll)
    m.missing_rate_shifts = int(row["missing_shifts"])
    m.missing_rate_hours = float(row["missing_hours"])
    return m


BUDGET_SQL = """
SELECT department, sum(budget_revenue_cents) AS cents,
       sum(budget_attendance) AS attendance
FROM budget_daily
WHERE venue_code IN {venues} AND date BETWEEN $start AND $end
GROUP BY department
"""


def budget(scope: Scope, start: date, end: date) -> dict[str, tuple[int, float]]:
    """Return budget revenue cents and attendance by department."""
    rows = scope.query(BUDGET_SQL, {"start": start, "end": end}).fetchall()
    return {d: (int(c or 0), float(a or 0)) for d, c, a in rows}


DAILY_SQL = """
WITH days AS (
    SELECT unnest(generate_series($start::DATE, $end::DATE, INTERVAL 1 DAY))::DATE
        AS d
), t AS (
    SELECT business_date AS d, sum(attendance) AS att,
           sum(ticket_revenue_cents) AS tix
    FROM daily_tickets
    WHERE venue_code IN {venues} AND business_date BETWEEN $start AND $end
    GROUP BY 1
), p AS (
    SELECT business_date AS d, sum(revenue_cents) AS pos
    FROM daily_pos
    WHERE venue_code IN {venues} AND business_date BETWEEN $start AND $end
    GROUP BY 1
), e AS (
    SELECT event_date AS d, sum(revenue_cents) AS events
    FROM daily_private_events
    WHERE venue_code IN {venues} AND event_date BETWEEN $start AND $end
    GROUP BY 1
), c AS (
    SELECT business_date AS d,
           count(*) FILTER (WHERE status = 'ok' AND feed IN ('tickets', 'pos'))
               AS ok_feeds
    FROM feed_coverage
    WHERE venue_code IN {venues} AND business_date BETWEEN $start AND $end
    GROUP BY 1
)
SELECT days.d, coalesce(t.att, 0) AS att,
       coalesce(t.tix, 0) + coalesce(p.pos, 0) + coalesce(e.events, 0) AS cents,
       coalesce(c.ok_feeds, 0) AS ok_feeds
FROM days LEFT JOIN t USING (d) LEFT JOIN p USING (d) LEFT JOIN e USING (d)
LEFT JOIN c USING (d)
ORDER BY days.d
"""


def daily_revenue(scope: Scope, start: date, end: date) -> list[dict]:
    """Return total revenue and attendance per day, unfiltered.

    A day where any scoped venue lacks ticket or POS rows has None values.
    """
    rows = scope.query(DAILY_SQL, {"start": start, "end": end}).fetchall()
    need = 2 * len(scope.venues)
    out = []
    for d, att, cents, ok_feeds in rows:
        complete = ok_feeds == need
        out.append(
            {
                "date": d,
                "attendance": int(att) if complete else None,
                "cents": int(cents) if complete else None,
            }
        )
    return out
