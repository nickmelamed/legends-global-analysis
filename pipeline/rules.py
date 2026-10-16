"""Business rules for the Attractions load, API and reconciliation.

Every rule that decides what a number means lives here, so the API and the
frontend never reimplement one. Evidence for each rule is in
docs/DATA_PROFILE.md and the decisions in docs/DECISIONS.md.
"""

from __future__ import annotations

import pandas as pd


class UnmappedLabel(ValueError):
    """A source value that no rule knows how to treat."""


# Tickets

# Each source system has its own status vocabulary. Cancelled lines keep their
# full quantity and value and record_status is ACTIVE on every row, so the
# status text is the only cancellation signal (DATA_PROFILE.md H2).
TICKET_STATUS_CANCELLED = {
    "LT": {"In Process": False, "Redeemed": False, "No Show": False, "Cancelled": True},
    "NT": {
        "CONFIRMED": False,
        "REDEEMED": False,
        "NO_SHOW": False,
        "PART_REDEEMED": False,
        "CANCELLED": True,
    },
}

ADMISSION_CLASSES = {"INDIVIDUAL", "GROUP", "FIT", "PROMOTION"}
# Add-ons (photo, parking) and private event entries are not visits (H3).
NON_ADMISSION_CLASSES = {"NON-ADMISSION", "EVENT"}


def is_cancelled(source_system: str, status: str) -> bool:
    """Return whether a ticket status means the line was cancelled.

    A status outside the source system's own vocabulary raises
    ``UnmappedLabel``, so a new status stops the load instead of being counted.
    """
    try:
        return TICKET_STATUS_CANCELLED[source_system][status]
    except KeyError:
        raise UnmappedLabel(
            f"ticket_status {status!r} is not known for source {source_system!r}"
        ) from None


def is_countable_ticket(source_system: str, status: str, package_class: str) -> bool:
    """Return whether a ticket line counts toward attendance and ticket revenue.

    Annual Pass visits ($0), no-shows and free admission count (D-004).
    """
    if package_class in NON_ADMISSION_CLASSES:
        admission = False
    elif package_class in ADMISSION_CLASSES:
        admission = True
    else:
        raise UnmappedLabel(f"package_class {package_class!r} is not mapped")
    return admission and not is_cancelled(source_system, status)


def countable_ticket_mask(df: pd.DataFrame) -> pd.Series:
    """Return a boolean mask of countable lines.

    Needs ``source_system``, ``ticket_status`` and ``package_class`` columns.
    """
    keys = df[["source_system", "ticket_status", "package_class"]]
    decided = {k: is_countable_ticket(*k) for k in set(map(tuple, keys.to_numpy()))}
    return pd.Series(
        [decided[tuple(k)] for k in keys.to_numpy()], index=df.index, dtype=bool
    )


def dedup_ticket_loads(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Keep the latest ``ingestion_ts`` for each ``ticket_line_id``.

    Returns the deduplicated frame and the number of rows dropped. The 262
    repeated ids in the source are identical apart from ``ingestion_ts`` (H1).
    """
    out = df.sort_values(
        ["ticket_line_id", "ingestion_ts"], kind="mergesort"
    ).drop_duplicates("ticket_line_id", keep="last")
    return out.sort_index(), len(df) - len(out)
