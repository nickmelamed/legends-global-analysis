"""The one place venue scope is applied.

Every query that touches venue data runs through ``Scope.query``, which binds
the venue list itself. A route never puts a venue from the request into SQL.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
from fastapi import HTTPException

from api.auth import User

DEFAULT_VENUE = "SSD"


@dataclass(frozen=True)
class Scope:
    """The signed-in user and the venues this request may read."""

    user: User
    venues: tuple[str, ...]
    con: duckdb.DuckDBPyConnection

    def query(self, sql: str, params: dict | None = None) -> duckdb.DuckDBPyRelation:
        """Run ``sql`` with ``{venues}`` replaced by a bound venue filter.

        ``sql`` must contain ``{venues}`` (for example
        ``WHERE venue_code IN {venues}``), so a scoped query cannot be written
        without the filter.
        """
        if "{venues}" not in sql:
            raise ValueError("a scoped query must filter on {venues}")
        bound = {f"_v{i}": v for i, v in enumerate(self.venues)}
        placeholders = "(" + ", ".join(f"${k}" for k in bound) + ")"
        return self.con.execute(
            sql.replace("{venues}", placeholders), {**(params or {}), **bound}
        )


def scoped_venues(user: User, requested: list[str] | None) -> tuple[str, ...]:
    """Return the venues a request may read.

    Raises 403 if any requested venue is outside the user's scope, including
    venues that do not exist, so the response never reveals which do. With no
    venue requested, return SSD if the user has it, else the user's first
    venue.
    """
    if not user.venues:
        raise HTTPException(status_code=403, detail="no venues in scope")
    if not requested:
        return (DEFAULT_VENUE,) if DEFAULT_VENUE in user.venues else user.venues[:1]
    outside = sorted(set(requested) - set(user.venues))
    if outside:
        raise HTTPException(status_code=403, detail="venue not in your scope")
    return tuple(dict.fromkeys(requested))
