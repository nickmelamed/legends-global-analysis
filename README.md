# Attractions

A web replacement for the Attractions Revenue Operations Center Power BI
report, built for the Legends Global take-home. It covers the Overview page
on the synthetic data, a repeatable load, venue scoping enforced by the
server, and "Ask the data", a grounded question box with a small eval.

Built with Claude Code under Nick Melamed's direction. docs/AI_LOG.md records
what the agent did and where it was wrong.

## Run it (about 5 minutes)

You need Docker Desktop (or Docker Engine with Compose v2.24 or later) and
the files supplied with the packet.

1. Clone the repo and copy the supplied folders into its root. They are not
   in git because the brand README says not to redistribute them (D-001):

   ```
   data/     the five workbooks, 01_Ticketing.xlsx to 05_Reference_Budget_Context.xlsx
   brand/    fonts/ and logos/ as supplied
   packet/   optional, only the docs link to it
   ```

2. Start everything:

   ```bash
   docker compose up --build
   ```

   `load` reads `data/`, writes `build/attractions.duckdb` and exits. `api`
   starts when the load succeeds and `web` serves the app. A cold build
   took 80 seconds on a laptop and the stack was serving 6 seconds later.

3. Open http://localhost:8080. The API is also at http://localhost:8000.

Settings come from `.env.example`. To change one, `cp .env.example .env` and
edit the copy, which compose reads on top of the example. `.env` is
gitignored.

- `APP_TODAY` is "today" for every date preset (default 2026-10-05). The
  system clock is never used.
- `DEV_USER` picks the signed-in user. `nick@dev` sees all three venues and
  `marcus@dev` sees only Summit Sky Deck. Requests can also send an
  `X-Dev-User` header. Asking for another venue's data returns 403.
- `ASK_CLIENT=recorded` (default) replays the model answers in
  `evals/recordings/`, so Ask works with no API key. `ASK_CLIENT=anthropic`
  with `ANTHROPIC_API_KEY` set calls the API live.

Check it:

```bash
curl -s "localhost:8000/api/overview?venue=SSD&preset=last_week" -H "X-Dev-User: nick@dev"
curl -s -o /dev/null -w "%{http_code}\n" "localhost:8000/api/overview?venue=RTL" -H "X-Dev-User: marcus@dev"   # 403
```

## Run it without Docker

Needs Python 3.12 and Node 20.

```bash
make setup                                   # pip install -e ".[dev]", npm ci, pre-commit
make load                                    # build/attractions.duckdb
uvicorn api.main:app --reload                # http://localhost:8000
npm --prefix web run dev                     # http://localhost:5173, proxies /api
```

## Check the numbers

```bash
make reconcile    # build/reports/reconciliation.md: ours vs the Power BI targets
make evals        # build/reports/evals.md: Ask the data against evals/cases.yaml
make ci           # lint, typecheck, tests, style
```

The targets are in `tests/fixtures/pbi_targets.json`. Summit Sky Deck for
2026-09-28 to 2026-10-04 matches to the dollar. Each difference is listed in docs/RECONCILIATION.md (R-001 to R-004).

## Where to read

| File | What it is |
|---|---|
| docs/WRITEUP.md | Part D: what was built, data issues, security, what was cut |
| docs/BACKLOG.md | Part B: stakeholder asks, needs, conflicts and what to build first |
| docs/AI_LOG.md | Part C and the AI usage log, phase by phase, mistakes included |
| docs/RECONCILIATION.md | Every difference from the Power BI targets, with the rows |
| docs/DATA_ISSUES.md | Each data fix and how much it moved the numbers |
| docs/DECISIONS.md | Decisions D-001 to D-016 and their reasons |
| docs/DATA_PROFILE.md | The profile of the workbooks and the hypothesis table |
| docs/SPEC.md | The phase plan |

## Layout

- `pipeline/` holds the load (`load.py`) and every business rule (`rules.py`).
- `api/` is FastAPI. `scope.py` is the one place venue scope is applied.
- `web/` is React, TypeScript and Vite.
- `evals/` holds the Ask cases, recordings and runner.
- `tests/` is pytest with small synthetic fixtures.
