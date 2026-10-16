"""Who is signed in.

In dev the user comes from the ``X-Dev-User`` header or ``DEV_USER``. In Azure,
Entra ID Easy Auth's ``X-MS-CLIENT-PRINCIPAL`` header would replace
``signed_in_email``. That parse is not built yet.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
from fastapi import HTTPException, Request


@dataclass(frozen=True)
class User:
    """A signed-in user and the venues they may see."""

    email: str
    display_name: str
    role: str
    venues: tuple[str, ...]


def signed_in_email(request: Request) -> str | None:
    """Return the signed-in email from the dev header or ``DEV_USER``."""
    return request.headers.get("x-dev-user") or request.app.state.settings.dev_user


def load_user(con: duckdb.DuckDBPyConnection, email: str | None) -> User:
    """Return the user with their venue scope, or raise 401 if unknown."""
    row = (
        con.execute(
            "SELECT email, display_name, role FROM app_users WHERE email = ?", [email]
        ).fetchone()
        if email
        else None
    )
    if row is None:
        raise HTTPException(status_code=401, detail="unknown user")
    venues = con.execute(
        "SELECT venue_code FROM user_venues WHERE email = ? ORDER BY venue_code",
        [email],
    ).fetchall()
    return User(row[0], row[1], row[2], tuple(v for (v,) in venues))
