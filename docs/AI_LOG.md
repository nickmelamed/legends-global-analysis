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

## Phase 1: profile the data (2026-10-15 23:44 to 2026-10-16 00:05)

Asked: start the timer, plan Phase 1, profile every sheet, test hypotheses 1
to 11 and the four Power BI cross-checks, and stop with the hypothesis table.

Produced: three profiling subagents ran in parallel (ticketing, POS, events
with labor and reference), each writing a script under `scripts/profile/`.
Claude recomputed the headline figures from the raw workbooks with separate
code before writing docs/DATA_PROFILE.md. All eight Summit targets reproduce
under one rule set, and so do the other two venues except a $1 rounding gap
in the Riverbend total. Found that POS has no duplicate loads (its repeated
rows are real lines), that the UTC timestamps are in NT tickets and not POS,
and that the Ancillary visual subtracts Bar twice.

Changed or rejected: Nick ruled on Bar, attendance, the missing Riverbend
day, Bar gaps, the channel chart and labor (D-003 to D-007). Nick asked to
reproduce the Ancillary visual as is. Claude pushed back, citing the
packet's instruction to say when a Power BI number is wrong. That question
is still open. The spec reviewer found that the profile scripts printed
order ids, guest country counts and the void reason into model context
during profiling. The scripts and docs were fixed, but the values had
already been read by a model. It also found a wrong count in D-006 (237
overlaps, of which 174 are unscheduled, not 237 unscheduled), weak
reasoning for rejecting POS UTC, and D-003 without a budget check. Each was
fixed with new script output. The style reviewer removed duplicated
cross-check text and resolved open questions.

What went wrong: rule 6 was not in the subagent prompts, so guest data
reached a model during profiling. `make ci` fails at lint on 33 existing
errors in `scripts/agent/` (protected) and `scripts/timer.py`. Typecheck and
tests cannot run before Phase 2.

Time: 20.7 active minutes against a 25 minute budget.

## Phase 2: rules, load and reconciliation (2026-10-16 05:47 to 06:07)

Asked: start the timer and plan Phase 2. Nick approved the plan, including
creating `pyproject.toml` and `tests/fixtures/pbi_targets.json` and editing
`.claude/gate-commands`.

Produced: `pipeline/rules.py`, `pipeline/load.py`, `pipeline/reconcile.py`,
98 tests, docs/RECONCILIATION.md, docs/DATA_ISSUES.md and D-009. Summit
matches all eight targets. Riverbend total revenue is $1 off because Power
BI adds rounded components (R-001). Every other target matches. Two loads
give byte-identical rollups in about 4 seconds.

Changed or rejected: the rule tests were written first and shown failing,
but the load tests were written after `load.py`. POS revenue moved to
integer cents before its tests first passed, and one muddled property-test
assertion was removed at the same point. The spec reviewer found three real
bugs. Department-days where every shift lacked a rate stored $0 payroll
instead of null (67 rows, none in the week). Week hours were rounded twice,
which could turn a miss into a match. And Claude had tagged its own derived
figures in R-004 with the `numbers: ok` marker meant for Power BI display
figures, so `make numbers` passed on numbers with no generated source. All
three were fixed with a failing test or a generated figure first. It also
asked for the ticket business-date rule to be a tested function, for
`record_type` to be validated, and for a blocking check that duplicate
ticket loads agree. Those were done too. Generating the R-004 figures showed
that DATA_PROFILE.md's 484.90 shift-rounded hours came from pandas rounding
binary floats. DuckDB gives 485.00 (half to even) and 485.40 (half up). All
three still display 3.81, so the conclusion stands. The style reviewer
removed section-banner comments and a few colons.

What went wrong: the numbers-marker misuse above, and a blanket string
rename in `rules.py` that mangled two names (caught by ruff). `make ci`
still fails at typecheck because `web/` does not exist. `make numbers`
fails because docs/WRITEUP.md does not exist yet. The check passes when run
on docs/RECONCILIATION.md alone.

Time: 19.8 active minutes against a 50 minute budget.

