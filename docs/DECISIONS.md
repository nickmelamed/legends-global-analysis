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
