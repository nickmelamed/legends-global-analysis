---
name: run-evals
description: Run the Ask the data eval cases and write build/reports/evals.md with pass or fail, grounding results and token cost per question.
disable-model-invocation: true
---

Run from the repo root and show the output of each step.

1. Say which client will run. `RecordedClient` is the default. The
   `AnthropicClient` runs only if `ANTHROPIC_API_KEY` is set in `.env`, and
   it costs money, so confirm with the owner before using it.
2. `make evals` and print `build/reports/evals.md`.
3. For each failed case, show the question, the expected answer from
   `evals/cases.yaml`, the reply, the tool outputs and the grounding result.
   Never edit `evals/cases.yaml` to make a case pass.
4. Report input and output tokens per case and the cost per question, with
   the price page URL and the date it was read.
5. If live responses were recorded, list the new files in
   `evals/recordings/` and check them for PII or free text before they are
   committed.
