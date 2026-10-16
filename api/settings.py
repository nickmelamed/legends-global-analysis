"""Settings read from the environment once, when the app is created."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """API settings, read once from the environment."""

    db_path: Path
    today: date
    dev_user: str | None
    ask_client: str = "recorded"
    ask_model: str = "claude-opus-5-5"
    recordings_dir: Path = Path("evals/recordings")

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from the environment (see ``.env.example``)."""
        return cls(
            db_path=Path(os.environ.get("DUCKDB_PATH", "build/attractions.duckdb")),
            today=date.fromisoformat(os.environ.get("APP_TODAY", "2026-10-05")),
            dev_user=os.environ.get("DEV_USER") or None,
            ask_client=os.environ.get("ASK_CLIENT") or "recorded",
            ask_model=os.environ.get("ANTHROPIC_MODEL") or "claude-opus-5-5",
            recordings_dir=Path(
                os.environ.get("ASK_RECORDINGS_DIR") or "evals/recordings"
            ),
        )
