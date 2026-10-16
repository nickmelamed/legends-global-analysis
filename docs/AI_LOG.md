# AI log

Factual entries, one per phase. What Nick asked, what Claude produced, what
Nick or the reviewers changed or rejected, and the time. Times come from
Nick's timer. Claude's clock times are in brackets for reference.

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

Changed or rejected: TBD after Nick's review.

Time at checkpoint: TBD (Nick's timer).
