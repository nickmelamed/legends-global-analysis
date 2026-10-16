# Progress

Current phase and what is left. Claude updates this at the end of each
phase. The "Now" section is shown to Claude at the start of each session and
after compaction.

## Now

- [x] Setup: repo-standards mode A, hooks, rules, reviewer agents, repo skills
- [x] Phase 1: profile the data, hypothesis table (about 25 min). Stop after.

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

Resolved in Phase 1: Bar rolls into Restaurant (D-003). Annual Pass visits,
no-shows and the RTL 2026-05-09 Free Admission Day count as attendance
(D-004). RTL 2026-04-18 is a missing feed (D-005). Cover shifts count and
the 0.5 h deduction stands. Payroll with missing rates is marked incomplete
(D-006). Bar gaps are closures and Affiliate stays off the channel chart
(D-007). Productivity shows 3.82. Power BI's 3.81 is likely per-shift rounding of hours (see DATA_PROFILE.md).

## Open questions for the owner

- D-001: may `data/`, `brand/` and `packet/` stay out of the repo, with the
  README telling reviewers to copy them in? (Nick is asking the hiring
  manager.)

From the Phase 1 profile (docs/DATA_PROFILE.md). Where Power BI already
answers a question, the profile follows Power BI until the owner says
otherwise.

- The Power BI Ancillary visual subtracts Bar twice, so its F&B is $7,979
  against the 9,230 target. Nick asked to reproduce the visual as is. That
  conflicts with the packet ("If you believe the Power BI number is wrong,
  say so and show why", and F&B is Restaurant, Bar and Cafe) and with D-003.
  The recommendation is to keep correct F&B and record the gap in
  docs/RECONCILIATION.md. Waiting on Nick.
- Some `booking_definite_date` values fall after 2026-10-05. Was the CRM
  export taken later than the other feeds?
