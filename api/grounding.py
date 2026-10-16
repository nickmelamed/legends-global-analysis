"""Check that every figure in a model reply comes from the tool outputs.

A number in the reply is grounded when some numeric value in the tool outputs
rounds to it at the precision the reply uses. An unsigned number may match
either sign ("fell 8.2%" for -8.23). A signed one must match its sign. A date
is grounded when the tool outputs contain it, and the years of those dates
count as numbers. Abbreviated amounts such as "$84.3K" and number words such
as "twelve" or "a third" never pass, since they cannot be checked.

The check is on values, not on which metric a value belongs to. "Attendance
was 91,891" passes if 91,891 is any value in the outputs, and the words
around a number ("rose", "fell") are not checked (D-015).
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
# Capitalised month names only, so "may 5" in prose is a number, not a date.
NAMED_DATE = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?"
    r"|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\b\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4})\b)?"
)
NUMBER = re.compile(
    r"(?<![\w.])[-+−]?\$?[-+−]?"
    r"(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)"
    r"(?:%|[kKmMbB]\b|\s(?:thousand|million|billion|bn)\b)?"
)
# "one" is left out because it is too common in prose to reject.
NUMBER_WORD = re.compile(
    r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"(?:thir|four|fif|six|seven|eigh|nine)teen|"
    r"(?:twen|thir|for|fif|six|seven|eigh|nine)ty|hundred|thousand|million|"
    r"billion|dozen|half|third|quarter|double|twice|triple)\b",
    re.IGNORECASE,
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
    # Half up is how people round. format() rounds a float's exact binary
    # value with ties to even. Accept either.
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
    signed = raw[0] in "+-"
    target = Decimal(raw)
    places = len(raw.split(".")[1]) if "." in raw else 0
    return any(
        target in _rounded(v, places)
        or (not signed and target in _rounded(abs(v), places))
        for v in numbers
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
    bad += [m[0] for m in NUMBER_WORD.finditer(text)]
    return Grounding(ok=not bad, ungrounded=bad)
