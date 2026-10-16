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
