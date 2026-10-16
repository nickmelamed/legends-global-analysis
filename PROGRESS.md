# Progress

Current phase and what is left. Claude updates this at the end of each
phase. The "Now" section is shown to Claude at the start of each session and
after compaction.

## Now

- [x] Setup: repo-standards mode A, hooks, rules, reviewer agents, repo skills
- [x] Phase 1: profile the data, hypothesis table (about 25 min). Stop after.
- [x] Phase 2: rules.py with tests, load, reconciliation (about 50 min)
- [x] Phase 2: write the Ancillary visual gap (D-008) and the RTL $1 rounding
  gap into docs/RECONCILIATION.md
- [x] Phase 3: API with scope helper and restricted-user tests (budget 20 min)
- [x] Phase 4: Overview page, screenshots at 390 and 1440, light and dark (budget 40 min)
- [x] Switch `.claude/gate-commands` to `make agent-check`
- [x] Phase 5: Ask the data, grounding check, evals (budget 40 min)
- [ ] Nick: `make evals RECORD=1` to record live answers, then Claude
  checks the recordings for PII, commits them and re-runs `make evals`

## Next

- [ ] Add `make numbers` to the gate once docs/WRITEUP.md exists
- [ ] Enable the project-checks step in `.github/workflows/agent-checks.yml`
- [ ] Phase 6: draft docs for Nick to rewrite

## Done

Resolved in Phase 1: Bar rolls into Restaurant (D-003). Annual Pass visits,
no-shows and the RTL 2026-05-09 Free Admission Day count as attendance
(D-004). RTL 2026-04-18 is a missing feed (D-005). Cover shifts count and
the 0.5 h deduction stands. Payroll with missing rates is marked incomplete
(D-006). Bar gaps are closures and Affiliate stays off the channel chart
(D-007). Productivity shows 3.82. Power BI's 3.81 is likely per-shift rounding of hours (see DATA_PROFILE.md). F&B
stays Restaurant + Bar + Cafe and the Ancillary visual's gap is documented
(D-008). Two bookings confirmed after 2026-10-05 stay unexplained, with no
KPI impact.

## Open questions for the owner

- D-001: may `data/`, `brand/` and `packet/` stay out of the repo, with the
  README telling reviewers to copy them in? (Nick is asking the hiring
  manager.)

