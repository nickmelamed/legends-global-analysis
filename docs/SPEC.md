# Spec

The packet in `packet/` is the source of truth for requirements, KPI
definitions and the data dictionary. This file records the plan Nick set and
the requirements he added. Section numbers are referenced from PROGRESS.md
and the AI log, so keep them stable.

The reconciliation week is 2026-09-28 to 2026-10-04. "Today" is `APP_TODAY`
(default 2026-10-05). Each phase ends with `/finish-phase`, an AI log entry,
and a stop for review.

## 1. Profile the data (about 25 min)

Profile every sheet in a subagent so the dumps stay out of the main context.
Write docs/DATA_PROFILE.md with row counts, keys, nulls, distinct values of
every status, label and category column, date ranges per source system, and
every value that looks like a duplicate or a different spelling.

Mark each hypothesis confirmed, rejected or partial, with evidence. Do not
assume any is true.

1. Duplicate loads. The same `ticket_line_id` (and POS line) appears more than
   once with a later `ingestion_ts`. Keep the latest and count the drops.
2. LT and NT status vocabularies differ. One marks cancellations explicitly,
   the other is unreliable. Find what a cancelled or refunded line looks like
   in each (status text, negative quantity, zero value, `record_status`).
3. Add-ons and private event entries in `dim_package` that are not admissions.
4. The 2026-02-03 cutover changes package names and channels. Package class
   is the stable key for last-year comparisons.
5. POS order-level subtotal, tax, gratuity and `final_total` repeat on every
   line. Revenue is `item_quantity * item_price - discount_amount` with voided
   lines excluded. Reconcile both ways.
6. Some POS timestamps are UTC and some local. Convert with
   `dim_venue.timezone`, then apply the 4 AM business-day cutoff.
7. Messy labels in outlet, department, venue code and position. Mapping
   tables, and unmapped values fail the load.
8. Labor. Overnight shifts belong to the start date. Missing rates.
   `total_hrs` vs `reg_hrs + ot_hrs` vs `actual_out - actual_in`. Tips are
   excluded from payroll.
9. Private events. Multi-day bookings repeat `booking_grand_total` on each
   event row, so use event-level money on the event date and count a booking
   once. Only Definite counts.
10. Missing venue-days, such as the Nashville day in April Priya mentioned.
11. Anything else found.

Cross-checks against `packet/Power_BI_Report_Export_Reference.pdf`:

- Ancillary shows Restaurant 4.5K, Bar 1.3K and Cafe 2.2K (about 8.0K of
  F&B) but the target F&B is 9,230. Gift Shop matches (7.0K vs 6,957). Find
  the definition behind each.
- Revenue by sales channel sums to about 61.0K but ticket revenue is 61,576.
  Affiliate is in ATP by channel but not in revenue by channel. Possibly a
  hidden visual filter.
- Productivity 1,849 / 484.5 is 3.82, but the report shows 3.81, which fits
  about 485.0 hours.
- The private events monthly chart stops at 2026-08.

Stop after this phase and show the hypothesis table.

## 2. Pipeline and reconciliation (about 50 min)

Failing tests first for each confirmed rule, one tiny synthetic fixture per
rule (duplicates, cancelled per source, UTC, cutover, repeated order totals,
missing rates, overnight shift, multi-day booking). Then build the load
described in D-002.

`tests/fixtures/pbi_targets.json` holds these targets exactly. Revenue must
match to the rounded dollar and hours to 0.1. Summit is required, the other
two are a stretch.

| Venue | Attendance | Ticket rev | F&B rev | Merch rev | Private events | Total rev | Labor hrs | Payroll |
|---|---|---|---|---|---|---|---|---|
| Summit Sky Deck | 1,849 | 61,576 | 9,230 | 6,957 | 6,565 | 84,328 | 484.5 | 9,347 |
| Riverbend Tower Lookout | 883 | 23,778 | 3,531 | 2,586 | 26,325 | 56,220 | 358.7 | 6,942 |
| Three Rivers Observatory | 771 | 20,283 | 2,769 | 1,979 | 17,565 | 42,596 | 321.2 | 6,258 |

`make reconcile` writes `build/reports/reconciliation.md` with ours, the
target, the difference and a status. Each miss gets an explanation in
docs/RECONCILIATION.md, and if the Power BI number looks wrong, the rows that
prove it. docs/DATA_ISSUES.md records each fix with its before and after
impact on the reconciliation week. Stop and show the reconciliation table.

## 3. API (about 20 min)

Endpoints: `/api/filters` (venues in scope, package classes, channels),
`/api/overview` (KPIs, labor KPIs, department revenue, pace to plan, each
with current, comparison, window dates and days elapsed),
`/api/trend?grain=day|week|month`, `/api/freshness`, `/api/export.csv`.
Exports carry the filters and the export time in the file.

Every endpoint goes through the scope helper. An out-of-scope venue returns
403. Tests cover a restricted user on every route, including export and ask.
Dev users: `nick@dev` sees all three venues, `marcus@dev` sees only Summit.

Comparison windows are the prior period (the preceding window of equal
length) or last year (dates minus 364 days). A last-year window that crosses
the 2026-02-03 cutover sets `crosses_cutover`. Pace to plan is actual over
budget for the days that have happened in the window, with `days_elapsed`
and `days_total`. Package class and sales channel filters apply only to
ticket metrics. The response flags this and the UI labels the affected
tiles. Log this as a decision.

## 4. Frontend Overview (about 40 min)

A 52px top bar: logo top left, then "Attractions", a Help & Support button, a
light/dark toggle and the signed-in user. A left sidebar about 240px wide
with tabs (Overview, Ticketing, F&B, Merchandise, Events, Pacing Report,
Cost Watch, then Support and Settings) and the filters below them. On a phone
the sidebar is a drawer. Each tab is a real route, the others are
placeholders.

Filters: venue, date preset (Last Week, Month to Date, Year to Date,
custom), package class, sales channel, compare (on or off, prior period or
last year). They live in the URL, persist across pages and have Reset.
Defaults: Summit Sky Deck, Last Week, Compare On, Prior Period. Light mode
by default.

KPI row: total revenue, total per cap, attendance, ticket revenue, each with
pace to plan. Labor row: payroll, labor hours, guests per labor hour, payroll
as % of revenue. Tiles have a small caps label, a big short-form value, a
delta with arrow and percent, and the comparison value with its dates. Cost
metrics invert the delta colour. Status uses a glyph or label as well as
colour. Pace bars: green at 100% or more, amber 90 to 99%, red under 90%,
always with the percentage as text. Revenue by department (Ticket,
Restaurant, Cafe, Merchandise, Private Events) shows the comparison. The
revenue trend has a Day/Week/Month toggle, the comparison as a dashed line,
and per cap on a second axis. A footer shows freshness with a stale warning.
Thin borders, no shadows, dense. Nicky Sans via @font-face.

Playwright screenshots at 390px and 1440px in light and dark.

## 5. Ask the data (about 40 min)

`POST /api/ask` with tools that wrap the Overview's functions:
`get_kpis(window, compare)`, `get_department_revenue`, `get_labor`,
`resolve_window(text)`. The venue comes from the signed-in user's scope and
is never a model argument. `LLMClient` has `RecordedClient` (default, replays
`evals/recordings/`) and `AnthropicClient` (when `ANTHROPIC_API_KEY` is set).
A grounding check extracts every number in the reply and rejects it if any
is missing from the tool outputs. On rejection or outage, return the tool
results as a plain table. No free text or PII reaches the model.

`evals/cases.yaml` has at least six cases with expected numbers computed from
the API: a last-year comparison, a labor question, a pace-to-plan question,
another venue as `marcus@dev` (must refuse), a no-data question such as
competitor prices (must say it does not know), and a prompt injection.
`make evals` writes `build/reports/evals.md`. Estimate cost per question from
logged tokens and the provider's price page, citing the source.

## 6. Docs (drafts, Nick writes the final text)

- docs/BACKLOG.md (Part B, one page): asks vs needs per stakeholder, the
  conflicts (all-venue visibility vs server-side scoping, solved with a
  role-based scope, speed vs accuracy, automation vs trust), what to build
  first and what not to build (no competitor price scraping, no free
  Open-Meteo tier in production), open questions, how usage is measured.
- docs/WRITEUP.md (Part D, 2 to 3 pages): architecture with a Mermaid
  diagram, 200 venues, the data issues table, hard parts and what was given
  up, how we know the numbers are right and how CI enforces it, security
  (Entra, scope, Key Vault references, what goes to the model), App Service
  with a staging slot, smoke test and rollback, what was cut.
- README.md: clone to running in under ten minutes, with a one-line note
  that it was built with Claude Code under Nick's design and review.
