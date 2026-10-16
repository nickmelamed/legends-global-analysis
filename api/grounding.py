"""Check that every figure in a model reply comes from the tool outputs.

A number in the reply is grounded when some numeric value in the tool outputs
rounds to it at the precision the reply uses, with or without its sign
("fell 8.2%" for -8.23). A date is grounded when the tool outputs contain it,
and the years of those dates count as numbers. Abbreviated amounts such as
"$84.3K" never pass, since they cannot be checked to the dollar.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun"]
        + ["jul", "aug", "sep", "oct", "nov", "dec"]
    )
}
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
NAMED_DATE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4})\b)?",
    re.IGNORECASE,
)
NUMBER = re.compile(
    r"(?<![\w.])[-+−]?\$?[-+−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"(?:%|[kKmMbB]\b|\s(?:thousand|million|billion|bn)\b)?"
)
ABBREVIATED = re.compile(r"([kKmMbB]|thousand|million|billion|bn)$")


@dataclass
class Grounding:
    """The result of a check. ``ungrounded`` lists figures as they appear."""

    ok: bool
    ungrounded: list[str] = field(default_factory=list)


def figures(text: str) -> list[str]:
    """Return every number in ``text`` as written, in order."""
    return [m.group(0) for m in NUMBER.finditer(text)]


def _leaves(obj, numbers: list[float], dates: set[date]) -> None:
    if isinstance(obj, dict):
        obj = list(obj.values())
    if isinstance(obj, list | tuple):
        for item in obj:
            _leaves(item, numbers, dates)
    elif isinstance(obj, bool) or obj is None:
        return
    elif isinstance(obj, int | float):
        numbers.append(float(obj))
    elif isinstance(obj, str) and (m := ISO_DATE.fullmatch(obj)):
        dates.add(date(int(m[1]), int(m[2]), int(m[3])))


def _rounded(value: float, places: int) -> set[Decimal]:
    # Half up is how people round. Half even is what Python's format() does
    # to a float, so a reply may use either.
    exp = Decimal(1).scaleb(-places)
    return {
        Decimal(repr(value)).quantize(exp, ROUND_HALF_UP),
        Decimal(value).quantize(exp, ROUND_HALF_EVEN),
    }


def figure_ok(token: str, numbers: Iterable[float]) -> bool:
    """Return whether figure ``token`` rounds from one of ``numbers``."""
    token = token.strip()
    if ABBREVIATED.search(token):
        return False
    raw = token.replace("−", "-").replace("$", "").replace(",", "").rstrip("%")
    target = Decimal(raw.replace("+", ""))
    places = len(raw.split(".")[1]) if "." in raw else 0
    return any(
        target in _rounded(v, places) | _rounded(abs(v), places) for v in numbers
    )


def _named_date_ok(m: re.Match, dates: set[date]) -> bool:
    month, day = MONTHS[m[1][:3].lower()], int(m[2])
    year = int(m[3]) if m[3] else None
    return any(
        d.month == month and d.day == day and (year is None or d.year == year)
        for d in dates
    )


def check(reply: str, tool_outputs: list) -> Grounding:
    """Return whether every number and date in ``reply`` is in ``tool_outputs``."""
    numbers: list[float] = []
    dates: set[date] = set()
    _leaves(tool_outputs, numbers, dates)
    numbers += [float(d.year) for d in dates]
    bad: list[str] = []

    def iso(m: re.Match) -> str:
        if date(int(m[1]), int(m[2]), int(m[3])) not in dates:
            bad.append(m[0])
        return " "

    def named(m: re.Match) -> str:
        if not _named_date_ok(m, dates):
            bad.append(m[0])
        return " "

    text = NAMED_DATE.sub(named, ISO_DATE.sub(iso, reply))
    bad += [t for t in figures(text) if not figure_ok(t, numbers)]
    return Grounding(ok=not bad, ungrounded=bad)
