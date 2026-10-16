"""Settings read from the environment once, when the app is created."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """What the API needs to know about its environment."""

    db_path: Path
    today: date
    dev_user: str | None

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from ``DUCKDB_PATH``, ``APP_TODAY`` and ``DEV_USER``."""
        return cls(
            db_path=Path(os.environ.get("DUCKDB_PATH", "build/attractions.duckdb")),
            today=date.fromisoformat(os.environ.get("APP_TODAY", "2026-10-05")),
            dev_user=os.environ.get("DEV_USER") or None,
        )
