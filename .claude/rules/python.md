---
paths:
  - "pipeline/**"
  - "api/**"
  - "evals/**"
  - "tests/**"
  - "scripts/*.py"
---

# Python (pipeline, API, evals)

- Python 3.12. `ruff check` and `ruff format` are the lint and format
  authority. NumPy docstrings (ruff pydocstyle convention `numpy`).
- Business rules live only in `pipeline/rules.py`. The API imports them. If a
  route needs a date window, it calls `api/windows.py`, which uses the rules.
- Money is computed in SQL or Decimal-safe pandas, and rounded only for
  display or reconciliation comparison, never before summing.
- The API opens DuckDB read-only. Every query that touches venue data goes
  through the scope helper, which takes the signed-in user, not a venue id
  from the request.
- "No data" is `None` (SQL NULL) in rollups and JSON, never 0. Fill with zero
  only where a row exists and its value is genuinely zero.
- Timestamps: convert to the venue's `dim_venue.timezone` first, then apply
  the 4 AM business-day cutoff. Never assign a business day from a naive
  timestamp whose zone is unknown.
- The load fails loudly (non-zero exit, message naming the value and sheet)
  on an unmapped label, a missing input file, or a failed data quality check
  marked blocking. It never silently drops rows.
- Read xlsx with `pd.read_excel(..., engine="calamine")`.
- Model calls go through `LLMClient`. Payloads to a model are built from an
  allowlist of fields, never by passing a DataFrame or row dict through.
