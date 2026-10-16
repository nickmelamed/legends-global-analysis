---
name: record-ruling
description: Record Nick's answer to an open question as a numbered decision, close the question in PROGRESS.md, point the docs at the decision, and commit.
disable-model-invocation: true
---

Use when Nick answers one or more questions from "Open questions for the
owner" in PROGRESS.md. Show the diff before committing.

1. Before writing anything, check each answer against the packet
   (extracted text, never the raw HTML), SPEC.md and the existing decisions.
   If an answer conflicts with any of them, quote the conflicting line,
   give a recommendation and stop for Nick's reply. Do not record it yet.
2. If a ruling rests on a data claim ("nothing indicates closure", "it is
   systematic"), check it with a query. Add that query to the relevant
   script in `scripts/profile/` (or the pipeline once it exists) so the
   figure can be reproduced. Never cite a number that no committed script
   prints.
3. Append one entry per ruling, or per closely related group, to
   docs/DECISIONS.md. Use the next D-number, today's date (APP_TODAY does
   not apply to log dates), and the Context, Decision, Why and
   Consequences sections. Put Nick's reason in Why with the evidence from
   step 2. Under Consequences, say which KPIs or screens it changes,
   including ratio KPIs.
4. In PROGRESS.md, delete the answered questions from "Open questions for
   the owner" and add one sentence per decision to the "Resolved" paragraph
   under Done. If a ruling creates work for a later phase, add it to Next.
5. Search docs/DATA_PROFILE.md (and docs/RECONCILIATION.md and
   docs/DATA_ISSUES.md once they exist) for text that still calls the
   question open. Replace it with the outcome and the D-number.
6. Run `python3 scripts/agent/check_style.py` on the changed files and
   `ruff check` on any changed script.
7. Commit as `docs(decisions): ...`, with any script change in its own
   `fix(profile)` or `feat(...)` commit. Do not push.
