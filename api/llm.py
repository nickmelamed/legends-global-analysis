"""Model clients for Ask the data.

``RecordedClient`` replays model turns from ``evals/recordings/`` and is the
default, so tests, CI and reviewers without a key never call a model.
``AnthropicClient`` calls the API. ``RecordingClient`` wraps it to write new
recordings for ``python -m evals.run --record``.

A response is a plain dict: ``content`` (text, tool_use and thinking blocks),
``stop_reason``, ``usage`` and ``model``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol

MAX_TOKENS = 4000


class LLMError(RuntimeError):
    """The model could not be reached or returned an error."""


class NoRecording(LLMError):
    """``RecordedClient`` has no recording for this question."""


class LLMClient(Protocol):
    """A client that returns the model's next message for a conversation."""

    model: str

    def create(self, system: str, tools: list, messages: list) -> dict:
        """Return the model's next message for ``messages``."""
        ...


def recording_key(messages: list) -> str:
    """Return the recording file stem for a conversation's first message."""
    first = messages[0]["content"]
    return hashlib.sha256(first.strip().lower().encode()).hexdigest()[:16]


class RecordedClient:
    """Replay recorded turns. The Nth call returns the Nth recorded turn."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.model = "recorded"

    def create(self, system: str, tools: list, messages: list) -> dict:
        """Return the recorded turn that follows ``messages``."""
        path = self.directory / f"{recording_key(messages)}.json"
        if not path.exists():
            raise NoRecording("no recorded answer for this question")
        recording = json.loads(path.read_text())
        turn = sum(1 for m in messages if m["role"] == "assistant")
        if turn >= len(recording["turns"]):
            raise NoRecording("the recording ends before this turn")
        self.model = recording["model"]
        return recording["turns"][turn]


class AnthropicClient:
    """Call the Claude API with the official SDK."""

    def __init__(self, model: str):
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(max_retries=1, timeout=60.0)
        self.model = model

    def create(self, system: str, tools: list, messages: list) -> dict:
        """Return the model's next message, or raise ``LLMError``."""
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system,
                tools=tools,
                messages=messages,
                output_config={"effort": "low"},
            )
        except self._anthropic.APIStatusError as e:
            raise LLMError(f"model returned HTTP {e.status_code}") from e
        except self._anthropic.APIConnectionError as e:
            raise LLMError("model unreachable") from e
        out = response.to_dict()
        return {
            "content": out["content"],
            "stop_reason": out["stop_reason"],
            "usage": {
                "input_tokens": out["usage"]["input_tokens"],
                "output_tokens": out["usage"]["output_tokens"],
            },
            "model": out["model"],
        }


class RecordingClient:
    """Call ``inner`` and keep each turn so it can be saved as a recording."""

    def __init__(self, inner: LLMClient, directory: Path):
        self.inner = inner
        self.directory = directory
        self.model = inner.model
        self.turns: list[dict] = []
        self.key: str | None = None

    def create(self, system: str, tools: list, messages: list) -> dict:
        """Return ``inner``'s turn and remember it."""
        if len(messages) == 1:
            self.turns, self.key = [], recording_key(messages)
        turn = self.inner.create(system, tools, messages)
        self.turns.append(turn)
        return turn

    def save(self, question: str) -> Path | None:
        """Write the turns of the last conversation, if there was one."""
        if not self.key:
            return None
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{self.key}.json"
        path.write_text(
            json.dumps(
                {"question": question, "model": self.model, "turns": self.turns},
                indent=2,
            )
            + "\n"
        )
        self.key = None
        return path
