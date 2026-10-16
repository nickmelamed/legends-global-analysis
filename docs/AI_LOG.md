# AI log

Factual entries, one per phase. What Nick asked, what Claude produced, what
Nick or the reviewers changed or rejected, and the time. Times are active
minutes from docs/TIME_LOG.md, which `scripts/timer.py` writes when Nick says
start time or pause time.

## Setup (started [21:13 PDT, 2026-10-15])

Asked: install the repo-standards tooling in mode A with the setup answers
given in the prompt, pin the model to claude-opus-5-5, set the reviewer
agents to `model: inherit`, and stop to show the hook smoke tests.

Produced: moved the HTML and PDF attachments into `packet/` (they were at the
root). Ran `git init` on `main`. Wrote CLAUDE.md, docs/SPEC.md,
docs/DECISIONS.md (D-001, D-002), PROGRESS.md, the Makefile, `.gitignore`,
`.env.example`, Python and TypeScript rule files, protected paths, and two
repo skills (`reload-and-reconcile`, `run-evals`), then ran the installer and
the smoke test.

Changed or rejected: Nick asked for the timer to be tracked by Claude
instead of by hand. Added `scripts/timer.py` and docs/TIME_LOG.md.

Time at checkpoint: setup was done before the timer started and is not
counted.
