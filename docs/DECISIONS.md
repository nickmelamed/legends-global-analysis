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
