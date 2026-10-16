# Decisions

One entry per decision that someone might later question. Newest last.
Nick edits these into his own words, since reviewers read this file to see
how he thinks.

## D-001: Supplied data, brand and packet stay out of git (2026-10-15)

Context. The brand README says "Do not redistribute these files." The
reviewers already have the packet and the workbooks.

Decision. `data/`, `brand/`, `packet/`, `build/` and `*.duckdb` are
gitignored. The README tells reviewers to copy `data/` and `brand/` into the
repo root. The load fails with a clear message naming the missing files.

Why. Committing the brand assets would redistribute them. Committing the
workbooks adds nothing the reviewers lack.

Consequences. A fresh clone does not run until the files are copied in, which
costs the reviewer one step. Status: Nick is asking the hiring manager
whether this is acceptable. Open until they answer.

## D-002: Stack (2026-10-15)

Context. The app replaces a read-only Power BI report. Data arrives as five
workbooks and is rebuilt in batch. It has to run from the README with
`docker compose up` in under ten minutes, and later on Azure.

Decision.

- `pipeline/`: `python -m pipeline.load` reads the xlsx files with
  python-calamine through pandas, cleans and conforms them, and writes
  `build/attractions.duckdb` with row-level facts, daily rollups by venue,
  date, package class and sales channel, a `load_runs` table and a
  `data_quality` table with one row per check per run. It builds into a temp
  file and swaps it in, so it is idempotent. Two runs give byte-identical
  rollups, and a test asserts that.
- `api/`: FastAPI reading DuckDB read-only. `windows.py` resolves a preset or
  custom range into the current and comparison windows and returns both in
  every response. Auth in dev is a header or `DEV_USER`, mapped through
  `app_users` and `user_venues`. In Azure, Entra ID Easy Auth's
  `X-MS-CLIENT-PRINCIPAL` header replaces it.
- `web/`: React, TypeScript and Vite, served by nginx in its own container.
  Recharts for charts.
- `docker-compose.yml`: a one-shot load service, then api and web.
- `APP_TODAY` (default 2026-10-05) is "today". The stale-data warning compares
  the last load and the max data date against it.

Why. DuckDB instead of Postgres Flexible Server, because the app is
read-only, the load is a batch rebuild, and it removes a container. Rejected
for now: Postgres (more moving parts for no benefit at three venues).

Consequences. At 200 venues and with concurrent writes, move to Postgres with
the same SQL. A DuckDB file cannot be shared by several writers, so the load
and the API must not write at the same time.

## D-003: Bar revenue rolls into Restaurant (2026-10-16)

Context. POS has four outlets (Restaurant, Cafe, Bar, Gift Shop). The
Overview's department split and `budget_daily` have Restaurant and Cafe but
no Bar. Summit's Bar revenue in the reconciliation week is $1,251.02.

Decision. Bar is reported under Restaurant in the department split and the
budget comparison. F&B stays Restaurant + Bar + Cafe, as the packet defines.

Why. The budget points the same way. With Bar added, Restaurant actuals
run at 69 to 76% of the Restaurant budget, close to Cafe's 73 to 84%. Bar
added to Cafe would put Cafe at 125 to 144% of plan (`pos.py`, Restaurant
budget section, 2025 and 2026 to date). Bar and Restaurant also both sell
alcohol and add a 20% gratuity, while Cafe sells neither.

Consequences. Summit's Restaurant line for the week is $7,035.30. The
mapping lives in `pipeline/rules.py` with a test.

## D-004: What counts as attendance (2026-10-16)

Context. Power BI counts Annual Pass visits ($0 value), no-shows and the one
Free Admission Day (RTL 2026-05-09, 142 lines).

Decision. All three count as attendance. Cancelled lines and the
NON-ADMISSION and EVENT package classes do not.

Why. It matches the Power BI targets (1,849 at Summit), and Nick confirmed
each one. Excluding passes would give 1,781, and excluding no-shows 1,772.

Consequences. Attendance means tickets issued for a visit date, not
turnstile entries. Per cap and ATP include the $0 pass visits.

## D-005: RTL 2026-04-18 is a missing feed (2026-10-16)

Context. Riverbend has no ticket rows and no POS rows on 2026-04-18, a
Saturday, but labor shows a normal staffed day.

Decision. Treat it as a missing feed. Ticket, F&B and merchandise show "no
data" for that venue-day, never zero.

Why. Priya (Revenue and Finance) recalls "a day in Nashville in April
where nothing loaded" in the stakeholder interviews. Nothing in the data
points to a closure. Labor shows 9 shifts and
55.15 hours that day, in line with the surrounding week (6 to 10 shifts).
The days either side had 150 and 206 guests.

Consequences. Any window containing that day carries a data gap flag, and
Riverbend's April trend shows a gap rather than a dip. Labor
exists that day, so ratio KPIs (per cap, guests per labor hour, labor $ per
guest, payroll as % of revenue) for any window containing it carry the same
flag.

## D-006: Labor hours and incomplete payroll (2026-10-16)

Context. Labor has 237 shifts that overlap the same person's previous
shift (174 of them unscheduled covers), 132 shifts with hours but no rate or earnings, and
a 0.5 h deduction on 12,004 shifts (every shift over 6 h on the clock and
every unscheduled shift).

Decision. Cover shifts count toward labor hours. `total_hrs` is the hours
measure, so the 0.5 h deduction stands. Payroll sums exported earnings, and
any window with a missing-rate shift is marked incomplete with the number of
shifts and hours affected. Payroll is not estimated.

Why. Power BI counts the cover shifts, and the targets only match with them.
The deduction is systematic, which points to an unpaid meal break by policy.
Rates change on almost every shift, so a filled rate would be a guess.
Showing $0 as if complete understates Summit's week by about $267.

Consequences. Summit's week shows $9,347 payroll marked incomplete (2
shifts, 12.98 h). Payroll as % of revenue carries the same flag.

## D-007: Bar outlet gaps are closures, Affiliate stays off the channel chart (2026-10-16)

Context. Some days have POS rows for a venue but none for its Bar (26 days
at RTL excluding 2026-04-18, 67 at TRO, 2 at SSD). Separately, Power BI's
revenue-by-channel visual leaves out Affiliate ($681.12 at Summit this
week).

Decision. A Bar gap on a day when the venue's other outlets have rows is a
closure or a no-sale day, so Bar shows $0 for that day, not "no data". The
revenue-by-channel chart leaves out Affiliate as Power BI does. Affiliate
stays in ticket revenue and in ATP by channel.

Why. The feed was live on those days, and the gaps fall mostly on Monday to
Wednesday at venues where Bar's median is 2 or 3 orders a day. Nick asked to
keep the channel chart as Power BI shows it.

Consequences. The channel chart does not sum to ticket revenue. The chart
gets a note saying Affiliate is excluded and by how much.

## D-008: Show correct F&B, document the Ancillary visual's gap (2026-10-16)

Context. The Power BI Ancillary visual shows Summit's Restaurant at $4.5K,
which is Restaurant minus Bar (4,533.26). Bar is then shown again on its own,
so the visual's F&B is 7,979.40 against the 9,230 target. The headline
$14.9K, the $8.08 per cap and the +24.6% vs prior all fit the same double
subtraction.

Decision. The app shows F&B as Restaurant + Bar + Cafe (9,230.42 for
Summit) and does not copy the visual. The $1,251.02 gap and the rows behind
it go in docs/RECONCILIATION.md.

Why. The packet defines F&B as Restaurant, Bar and Cafe, and asks
candidates to say so when a Power BI number is wrong. The 9,230 target
itself uses the full sum.

Consequences. Anyone comparing the app with the old Ancillary page will
see Restaurant and ancillary totals $1,251.02 higher at Summit for the week.
The reconciliation doc has to explain this before users see it.

## D-009: Guest data and free text stay out of the database (2026-10-16)

Context. The workbooks carry `customer_country`, ticket and POS `order_id`,
labor `person_id`, and free-text `comments`, `voided_reason` and
`lost_reason_name`. No Overview measure needs them, and Phase 5 puts a
language model behind the API.

Decision. The load reads these columns for in-load checks only (order
subtotals, shift overlaps, business-key duplicates) and does not write them to
DuckDB. A test asserts that no output table has one of these columns.

Why. A column that is not in the database cannot be sent to a model, exported
or shown by mistake. That is simpler to verify than an allowlist on every
query.

Consequences. Measures that need these fields, such as orders per guest or
average check, need the load changed first. Average check needs an order
count, which can be added as a count column without the ids.

## D-010: Package class and channel filters apply to ticket metrics only (2026-10-16)

Context. The packet lists package class and sales channel as global
filters, but they only exist on ticket rows. F&B, merchandise, private
events and labor have no package class or channel.

Decision. The filters change attendance, ticket revenue, ATP and the Ticket
department bar. Total revenue, per cap, labor, the other departments and the
revenue trend use every ticket. Each metric in `/api/overview` carries
`ticket_filtered`, and the response lists `ticket_filter_applies_to`, so the
UI can label the tiles. Pace to plan is null for filtered metrics.

Why. Total revenue built from filtered tickets plus unfiltered F&B would be a
number that means nothing. Per cap needs total revenue and attendance from the
same guests. The budget has no class or channel split, so a filtered pace
would compare a slice with the whole plan. Nick chose this over letting the
filter flow into total revenue.

Consequences. With a filter set, per cap does not equal total revenue over
the attendance tile shown next to it. The UI has to say so on the tile.

## D-011: Date presets end yesterday (2026-10-16)

Context. With APP_TODAY 2026-10-05, the data runs through 2026-10-04. Today's
business day runs to 4 AM tomorrow, so it has not closed.

Decision. Every preset ends the day before APP_TODAY, the last complete business day.
`days_total` is the whole week, month or year, and `days_elapsed` counts the
days up to yesterday. On the first of a month, Month to Date is the whole
previous month. Pace compares actual and budget over the elapsed days only,
including in a custom range that runs into the future.

Why. A window that includes today would show a partial day as a dip. Nick
chose this.

Consequences. On 2026-10-05, Month to Date is 2026-10-01 to 2026-10-04 (4 of
31 days). Its prior period is 2026-09-27 to 2026-09-30. A custom range that
runs past yesterday shows actuals up to yesterday only, since tickets hold
presales and private events hold future bookings. Its comparison covers the
same number of days from the comparison start.

## D-012: No delta or pace colour over missing data (2026-10-16)

Context. A window can hold a no-data day, such as RTL 2026-04-18, and a
comparison window can start before the data does (2025-01-01). Summing what
is there makes the missing days look like a drop or a rise.

Decision. Each metric carries `data_gap` and `comparison_data_gap`. When
either is set, `delta_pct` is null. The current and comparison values are
still returned with their flags. Pace keeps its percentage but has no
green, amber or red status over a gap. Private events have no feed of their
own, so a day counts as loaded for them when any feed covers the venue that
day. Outside those days they are no data, not $0.

Why. Rule 4 says missing data never shows as a dip. A percentage change
over different amounts of data is not a change in the business.

Consequences. RTL's week of 2026-04-13 shows total revenue and attendance
with a gap flag and no delta. Labor, which has rows that day, keeps its
delta. The spec reviewer found the original behaviour, and Nick has not yet
ruled on it.
