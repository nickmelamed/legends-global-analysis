# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and versions follow Semantic Versioning.

## Unreleased

### Added

- Workbook profiling scripts in `scripts/profile/` and docs/DATA_PROFILE.md
  with the hypothesis table and Power BI cross-checks.
- Decisions D-003 to D-007 on Bar revenue, attendance, the missing Riverbend
  day, labor hours and payroll, Bar gaps and the channel chart.
- `pipeline/rules.py` with unit and property tests for every business rule:
  ticket dedup, per-source cancel status, admission classes, timezone and the
  4 AM business day, POS line revenue in cents, outlet and labor department
  mapping, shift measures, private events, comparison windows, the cutover
  and missing-data status.
- `make load` builds `build/attractions.duckdb` with facts, daily rollups,
  feed coverage, dev users, `load_runs` and `data_quality`, atomically.
- `make reconcile` writes `build/reports/reconciliation.md` and `.json`.
  Summit matches all eight targets.
- docs/RECONCILIATION.md (R-001 to R-004), docs/DATA_ISSUES.md and D-009.
- `pyproject.toml` with pandas, duckdb, python-calamine, pytest, hypothesis
  and ruff.
- Rules for the Last Week, Month to Date and Year to Date presets, the last
  elapsed day, the aligned comparison end, the cutover flag, a None-safe
  ratio and percent change, and pace status thresholds.
- `api/`: FastAPI over the DuckDB rollups with `/api/filters`,
  `/api/overview`, `/api/trend`, `/api/freshness` and `/api/export.csv`.
  One scope helper binds the venue filter in every query, and an
  out-of-scope venue is a 403. Tests cover every route as a restricted user,
  and a slow test checks the overview against the Power BI targets.
- Decisions D-010 (ticket filters), D-011 (date presets end yesterday) and
  D-012 (no delta or pace colour over missing data).
- fastapi and uvicorn dependencies, with httpx2 for the test client.
- Custom ranges are capped at 731 days. The export header shows days
  elapsed, the comparison's elapsed end and whether a window crosses the
  cutover.
- `web/`: React, TypeScript and Vite Overview. It has the branded shell,
  a sidebar that becomes a drawer on a phone, a route for every tab, and
  URL filters with Reset. The page shows KPI and labor tiles with pace to
  plan, revenue by department, a revenue trend with a dashed comparison and
  per cap on the right axis, and a freshness footer. Missing days show as
  "No data" or a gap marker, never zero.
- Playwright tests for defaults, filters and Reset, missing data, the
  restricted user and layout at 390 and 1440 px in both themes.
  `npm --prefix web run screenshots` writes docs/screenshots/.
- Decisions D-013 (dual axis on the trend) and D-014 (dev-only npm audit
  findings), and docs/BACKLOG.md.
- The window in API responses carries `cutover_date`. The phone drawer
  closes on Escape, and the Help link has an accessible name.
- Ask the data: `POST /api/ask` with four scoped tools over the Overview
  code, a check that every figure in a reply is in the tool outputs, and a
  plain table when the check fails or the model is unavailable. Replies
  replay `evals/recordings/` unless `ASK_CLIENT=anthropic`.
- An Ask the data page with the answer and the figures it used.
- `evals/cases.yaml` with seven cases and `make evals` (`RECORD=1` to call
  the model), which writes build/reports/evals.md with cost per question.
- Decisions D-015 (how answers are checked) and D-016 (model and recordings).
- `docker compose up` runs the load once against the mounted `data/`, then
  the api and the web app on port 8080. Secrets, `data/` and `build/` stay
  out of the images.
- README.md, from clone to running.
- Drafts of docs/BACKLOG.md (Part B) and docs/WRITEUP.md (Part D).

### Changed

- The Stop gate runs ruff and the fast pytest suite as well as the style
  check.
- The Stop gate also runs `make numbers` on the write-up and the
  reconciliation notes.
- CI runs `make ci` on every push and pull request.
- The list of deferred work moved from docs/BACKLOG.md to the write-up.

### Fixed

- Escape on the phone drawer returns focus to the menu button.
