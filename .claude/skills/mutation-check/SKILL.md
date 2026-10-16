---
name: mutation-check
description: Prove a set of tests is not hollow. Break one behaviour at a time, run the tests that claim to cover it, confirm they fail, and restore the file exactly.
disable-model-invocation: true
---

Use after writing tests for a feature, before calling them done. Show the
output of every run. This skill never commits and must leave the tree as it
found it.

1. Run `git status --short` and record it. If a file you plan to mutate has
   uncommitted changes, back it up anyway. Restoring from git would lose them.
2. List the mutations first, one per behaviour the tests claim to cover. Each
   one names the file, the exact old and new text, and the test (pytest `-k`
   or Playwright `-g`) that should fail. Pick changes that a real bug could
   make, such as dropping a filter, returning 0 for None, skipping the scope
   check or swapping a comparison. Never mutate a test, a fixture,
   `tests/fixtures/pbi_targets.json` or `evals/cases.yaml`.
3. For each mutation, one at a time:
   - Copy the file to the scratchpad.
   - Apply the change with an exact replace that fails loudly if the old
     text is missing.
   - Run only the named tests and show the result.
   - Copy the backup back and check the old text is present again.
4. Make sure no reviewer or other agent is reading the same files while a
   mutation is live.
5. Run `git status --short` and compare with step 1. Then run the full suite
   (`make agent-check`, plus `npm --prefix web run e2e` if `web/` was
   touched) and show that it passes.
6. Report a table of mutation, expected failing test and result. A mutation
   that no test caught is a finding. Write the missing test, show it failing
   against the mutation, then restore. Record the outcome in the phase's
   AI log entry.
