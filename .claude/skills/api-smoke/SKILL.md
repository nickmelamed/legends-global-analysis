---
name: api-smoke
description: Start the API on the real database, check Summit's reconciliation week against the Power BI targets, check that a restricted user gets 403 on every route, and print the export header.
disable-model-invocation: true
---

Run from the repo root and show the output of each step. This skill only
reads. It never changes code, targets or fixtures.

1. Check that `build/attractions.duckdb` exists. If not, stop and say to run
   `make load` (or the reload-and-reconcile skill) first.
2. Start the API in the background on a free port:
   `DEV_USER=nick@dev APP_TODAY=2026-10-05 uvicorn api.main:app --port 8765`.
   Wait until `/api/freshness` answers, and stop the server at the end,
   including when a step fails.
3. Targets. As nick@dev, for each venue in `tests/fixtures/pbi_targets.json`,
   call `/api/overview?venue=<code>&start=<window start>&end=<window end>`.
   Compare attendance, ticket, F&B, merchandise, private events and total
   revenue, labor hours and payroll with the targets, using
   `pipeline.reconcile.compare`, so the rounding is the same as
   `make reconcile`. Print one table with ours, the target, the difference
   and the status. A required venue that misses is a failure. A known miss
   must have an R- entry in docs/RECONCILIATION.md; name it.
4. Scope. As marcus@dev, call every `/api` route the app registers (list them
   from `api.main.app.routes`, not from memory) with `venue=RTL`, then with
   `venue=SSD&venue=RTL`. Every call must be a 403. Then call each with no
   venue. Every call must be a 200 that mentions only SSD. Print a table of
   route, case and status code.
5. No data. As nick@dev, call `/api/overview?venue=RTL&start=2026-04-13&end=2026-04-19`
   and check that attendance has `data_gap` true, a null `delta_pct` and a
   pace with no status (D-005, D-012).
6. Freshness. Print `/api/freshness` for all three venues and say whether
   any feed is stale.
7. Export. Print the `#` header lines of `/api/export.csv` for marcus@dev.
8. Summarise in a few lines: targets matched or missed, scope failures (any is
   serious), and anything unexpected. Do not fix anything in this skill.
   Report and stop.

Rule 6 applies. The API returns rollups only, but never print raw fact rows
or any guest or free-text field.
