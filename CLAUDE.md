# Attractions (Legends Global take-home)

A time-boxed take-home for an AI Execution and Prototyping Analyst role at
Legends Global. Legends wants to replace a Power BI report (Attractions
Revenue Operations Center) for three fictional observation decks with a
branded web app on Azure. The deliverable is a working Overview page on
synthetic data, a repeatable load script, server-enforced venue scoping, one
grounded AI feature with a small eval, and short written docs. Good means the
Summit Sky Deck numbers for 2026-09-28 to 2026-10-04 reconcile to the dollar
against the targets, any differences are explained with evidence, and the app
runs from the README in under ten minutes with `docker compose up`. Reviewers
grade judgment, data skepticism and honesty over how much gets built. A small
thing that works beats a big thing that does not.

The packet is in `packet/`. Requirements, KPI definitions and the data
dictionary are in `Take_Home_Packet.html`. Known difficulties are in
`Technical_Migration_Brief.html`, interviews in `Stakeholder_Interviews.html`.
Each HTML file embeds about 500KB of base64 fonts, so extract the text
(strip tags and `<style>`/`data:` blobs) instead of reading raw HTML.

The phase plan is in docs/SPEC.md. Status and open questions are in
PROGRESS.md. Decisions are in docs/DECISIONS.md. "Today" is APP_TODAY
(default 2026-10-05), never the system clock.

## Non-negotiable rules

1. Every business rule (countable ticket, status handling per source system,
   business day 4 AM cutoff, timezone conversion, Monday to Sunday week,
   comparison windows, department mapping) lives in `pipeline/rules.py` and
   has a unit test. The API and the frontend never reimplement them.
2. Never edit a reconciliation target (`tests/fixtures/pbi_targets.json`) or
   an eval's expected answer (`evals/cases.yaml`) to make a test pass. If our
   number differs, record it in docs/RECONCILIATION.md with the query, the
   rows involved and the dollar gap.
3. Venue scope is applied in one query helper that every endpoint calls,
   including exports and the AI tools. Changing a URL or query parameter
   never returns another venue's data. An out-of-scope venue is a 403, never
   an empty result. Each route has a test with a restricted user.
4. Missing data is not zero. A venue-day with no rows from a feed shows
   "no data", never a zero or a dip.
5. The language model never produces a number. Numbers come from tool
   functions, and code checks that every figure in a reply appears in the
   tool output before the reply is returned.
6. Never send guest personal data (customer_country, order ids, person_id) or
   free-text fields (comments, notes, voided_reason, lost_reason_name) to a
   model. Free text is untrusted input.
7. Brand. Logo files from `brand/` exactly as supplied (black on light, white
   on dark, never recoloured, stretched or rotated). Nicky Sans is the only
   font. Chrome is black, white and grays. Gold #FFC000 is only for data
   highlights, never for UI.
8. Every data fix goes in docs/DATA_ISSUES.md: what was wrong, how it was
   detected, how it was fixed at the source, rows affected, and the dollar or
   count impact on the reconciliation week.
9. Secrets never go in the repo or images. Only `.env.example` is committed.
10. Never weaken a test, lint rule, or check to make it pass.
11. Ask before changing anything in `.claude/protected-paths`, the evaluation
    design, dependencies, CI, or hooks.

## Commands

```bash
make setup        # install Python and web dependencies
make load         # python -m pipeline.load -> build/attractions.duckdb
make reconcile    # build/reports/reconciliation.md
make evals        # build/reports/evals.md
make agent-check  # the fast checks the Stop hook runs
make ci           # exactly what CI runs
docker compose up # load, then api and web
```

## Where things live

- `pipeline/`: load script and `rules.py`. `api/`: FastAPI, `windows.py`, the
  scope helper, the ask endpoint. `web/`: React, TypeScript, Vite.
- `tests/`: pytest with tiny synthetic fixtures. `evals/`: cases and
  recordings. `build/`: generated database and reports (gitignored).
- `data/`, `brand/`, `packet/`: supplied files, gitignored, never edited.
- `docs/`: SPEC, DECISIONS, DATA_PROFILE, DATA_ISSUES, RECONCILIATION,
  BACKLOG, WRITEUP, AI_LOG.

## How to work here

- When Nick says "start time" or "pause time", run
  `python3 scripts/timer.py start` or `pause` and show the output. At each
  phase end run `python3 scripts/timer.py mark "end of Phase N"` and put the
  active minutes in the AI log entry.
- Phases end with `/finish-phase`, then stop and show evidence (commands and
  output). Nick reads every diff. Do not start the next phase unprompted.
- Append a factual entry to docs/AI_LOG.md at the end of each phase,
  including what went wrong. Do not polish it.
- If something runs about 15 minutes over its phase budget, stop and say so.
- Anything the requirements leave unclear goes in PROGRESS.md under "Open
  questions for the owner". Do not guess silently.
- Commit in small atomic Conventional Commits. Code and its tests go in the
  same commit. Ask before pushing or changing dependencies.
- If you repeat a multi-step procedure, propose a skill for it and wait.
