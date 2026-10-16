# Progress

Current phase and what is left. Claude updates this at the end of each
phase. The "Now" section is shown to Claude at the start of each session and
after compaction.

## Now

- [x] Setup: repo-standards mode A, hooks, rules, reviewer agents, repo skills
- [ ] Phase 1: profile the data, hypothesis table (about 25 min). Stop after.

## Next

- [ ] Phase 2: rules.py with tests, load, reconciliation (about 50 min)
- [ ] Switch `.claude/gate-commands` to `make agent-check` once tools exist
- [ ] Add `make numbers` to the gate once `build/reports` exists
- [ ] Enable the project-checks step in `.github/workflows/agent-checks.yml`
- [ ] Phase 3: API with scope helper and restricted-user tests (about 20 min)
- [ ] Phase 4: Overview page, screenshots at 390 and 1440, light and dark (about 40 min)
- [ ] Phase 5: Ask the data, grounding check, evals (about 40 min)
- [ ] Phase 6: draft docs for Nick to rewrite

## Done

## Open questions for the owner

- D-001: may `data/`, `brand/` and `packet/` stay out of the repo, with the
  README telling reviewers to copy them in? (Nick is asking the hiring
  manager.)

From the Phase 1 profile (docs/DATA_PROFILE.md). Where Power BI already
answers a question, the profile follows Power BI until the owner says
otherwise.

- The Overview splits F&B into Restaurant and Cafe, and the budget has no Bar
  line. Should Bar ($1,251.02 at Summit this week) roll into Restaurant or
  Cafe?
- The Power BI Ancillary visual subtracts Bar twice. The plan is to show the
  correct F&B and note the difference. Is that acceptable?
- Is RTL 2026-04-18 a closure or a missing feed? It has labor but no tickets
  or POS. Are the Bar-only outlet gaps closures?
- Should Annual Pass visits ($0) and no-shows count as attendance? Power BI
  counts both (68 passes and 77 no-shows at Summit this week).
- Is the revenue-by-channel visual a Top 7 filter, or is Affiliate excluded
  on purpose?
- Is the RTL 2026-05-09 Free Admission Day real?
- Should overlapping cover shifts count (2 shifts, 11.0 h at Summit this
  week)? Power BI counts them.
- Should payroll with missing rates show as incomplete instead of $0? Summit
  this week has 2 such shifts (12.98 h).
- Is the 0.5 h deduction on 5 h unscheduled shifts intended?
- Some `booking_definite_date` values fall after 2026-10-05. Was the CRM
  export taken later than the other feeds?
- Productivity. The target hours (484.5) give 3.82, but Power BI shows 3.81,
  which fits per-shift rounded hours (484.9). We plan to show 3.82 and
  explain it.
