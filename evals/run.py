"""Run the Ask the data cases and write ``build/reports/evals.md``.

``python -m evals.run`` replays ``evals/recordings/`` and costs nothing.
``python -m evals.run --record`` calls the Claude API with the key in
``ANTHROPIC_API_KEY`` (or ``.env``) and writes new recordings first.

Grading is deterministic: status code, required figures at any display
precision, phrases, and whether the model was called. No model grades a model.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from api.grounding import figure_ok, figures
from api.llm import AnthropicClient, RecordingClient
from api.main import create_app
from api.settings import Settings

CASES = Path("evals/cases.yaml")
REPORT = Path("build/reports/evals.md")
PRICE_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
PRICE_READ = date(2026, 10, 16)
# USD per million input and output tokens, base rates, no caching.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


@dataclass
class Outcome:
    """One case's result."""

    case: dict
    status: int
    body: dict
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return whether every expectation held."""
        return not self.failures


def grade(case: dict, status: int, body: dict) -> list[str]:
    """Return what the response got wrong for ``case``, or nothing."""
    exp = case["expect"]
    if status != exp["status"]:
        return [f"status {status}, expected {exp['status']}"]
    if status != 200:
        return []
    fails = []
    if body["model_called"] != exp["model_called"]:
        fails.append(f"model_called is {body['model_called']}")
    answer = body["answer"] or ""
    if body["fallback"] and not exp.get("allow_fallback"):
        fails.append(f"fell back: {body['fallback']}")
    found = figures(answer)
    for value in exp.get("figures", []):
        if not any(figure_ok(t, [value]) for t in found):
            fails.append(f"missing figure {value}")
    if exp.get("figures_any") and not any(
        figure_ok(t, exp["figures_any"]) for t in found
    ):
        fails.append(f"none of {exp['figures_any']}")
    low = answer.lower()
    if exp.get("phrases_any") and not any(p.lower() in low for p in exp["phrases_any"]):
        fails.append(f"none of the phrases {exp['phrases_any']}")
    for p in exp.get("forbidden", []):
        if p.lower() in low:
            fails.append(f"forbidden phrase {p!r}")
    if "max_figures" in exp and len(found) > exp["max_figures"]:
        fails.append(f"{len(found)} figures, at most {exp['max_figures']} allowed")
    if "venues" in exp and body["venues"] != exp["venues"]:
        fails.append(f"venues {body['venues']}")
    return fails


def cost(body: dict) -> float | None:
    """Return the dollar cost of the model calls, if the model has a price."""
    price = PRICES.get(body.get("model", ""))
    if price is None or not body.get("usage"):
        return None
    u = body["usage"]
    return (u["input_tokens"] * price[0] + u["output_tokens"] * price[1]) / 1e6


def load_env(path: Path) -> None:
    """Set variables from ``.env`` that the environment does not already have."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.startswith("#") and value:
            os.environ.setdefault(key.strip(), value.strip())


def run(record: bool) -> list[Outcome]:
    """Run every case and return the outcomes."""
    settings = Settings.from_env()
    app = create_app(settings)
    recorder = None
    if record:
        recorder = RecordingClient(
            AnthropicClient(settings.ask_model), settings.recordings_dir
        )
        app.state.llm = recorder
    client = TestClient(app)
    outcomes = []
    for case in yaml.safe_load(CASES.read_text()):
        r = client.post(
            "/api/ask",
            params={"venue": case.get("venue", [])},
            headers={"X-Dev-User": case["user"]},
            json={"question": case["question"]},
        )
        body = r.json() if r.status_code == 200 else {}
        if recorder:
            recorder.save(case["question"])
        outcomes.append(
            Outcome(case, r.status_code, body, grade(case, r.status_code, body))
        )
    return outcomes


def report(outcomes: list[Outcome], record: bool) -> str:
    """Return the Markdown report."""
    passed = sum(o.passed for o in outcomes)
    costs = [c for o in outcomes if (c := cost(o.body)) is not None]
    lines = [
        "# Ask the data evals",
        "",
        f"{passed} of {len(outcomes)} cases pass. "
        + ("Live model calls, recorded." if record else "Replayed recordings."),
        "",
        "| Case | User | Result | Status | Model | Grounded | Fallback | "
        "Tools | Tokens in/out | Cost |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for o in outcomes:
        b, c = o.body, cost(o.body)
        tools = ", ".join(t["name"] for t in b.get("tool_calls", [])) or "-"
        usage = b.get("usage") or {}
        lines.append(
            f"| {o.case['id']} | {o.case['user']} | "
            f"{'pass' if o.passed else 'FAIL'} | {o.status} | "
            f"{b.get('model', '-') if b.get('model_called') else 'not called'} | "
            f"{b.get('grounded', '-')} | {b.get('fallback') or '-'} | {tools} | "
            f"{usage.get('input_tokens', 0)}/{usage.get('output_tokens', 0)} | "
            f"{'-' if c is None else f'${c:.4f}'} |"
        )
    if costs:
        lines += [
            "",
            f"Mean cost per question that called the model: "
            f"${sum(costs) / len(costs):.4f}. Base prices from {PRICE_SOURCE} "
            f"(read {PRICE_READ.isoformat()}), without prompt caching.",
        ]
    lines += ["", "## Answers", ""]
    for o in outcomes:
        lines += [f"### {o.case['id']}", "", f"Q: {o.case['question']}", ""]
        if o.status != 200:
            lines.append(f"HTTP {o.status}, no model call.")
        else:
            lines.append(f"A: {o.body['answer'] or '(plain table shown)'}")
            if o.body.get("ungrounded"):
                lines.append(f"Ungrounded figures: {o.body['ungrounded']}")
        if o.failures:
            lines.append(f"Failures: {'; '.join(o.failures)}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Run the cases, write the report and return 1 if any case failed."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", action="store_true")
    record = parser.parse_args().record
    if record:
        load_env(Path(".env"))
    outcomes = run(record)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report(outcomes, record))
    (REPORT.parent / "evals.json").write_text(
        json.dumps(
            [
                {"id": o.case["id"], "passed": o.passed, "failures": o.failures}
                for o in outcomes
            ],
            indent=2,
        )
    )
    print(REPORT.read_text())
    return 0 if all(o.passed for o in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
