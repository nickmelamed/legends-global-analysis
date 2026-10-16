---
name: reload-and-reconcile
description: Rebuild the DuckDB twice from data/, check the rollups are byte-identical, run reconciliation against the Power BI targets and print the table.
disable-model-invocation: true
---

Run from the repo root and show the output of each step.

1. Check that `data/` holds the five xlsx files. If not, stop and say which
   are missing.
2. `make load`, then copy the rollup export to `build/run1/`.
3. `make load` again, then copy the rollup export to `build/run2/`.
4. `diff -r build/run1 build/run2`. Any difference is a failure. Report it
   and stop.
5. `make reconcile` and print `build/reports/reconciliation.md`.
6. For every row whose status is not a match, check that docs/RECONCILIATION.md
   has an entry with the query, the rows and the dollar gap. List any that
   are missing. Never change `tests/fixtures/pbi_targets.json`.
7. Print the latest `data_quality` rows that failed or warned.
