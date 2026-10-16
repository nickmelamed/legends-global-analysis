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

### Changed

- The Stop gate runs ruff and the fast pytest suite as well as the style
  check.

### Fixed
