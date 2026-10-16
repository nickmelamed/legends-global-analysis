#!/usr/bin/env python3
"""Track active time on the take-home against the four-hour budget.

Usage::

    python3 scripts/timer.py start [note]   # clock in
    python3 scripts/timer.py pause [note]   # clock out
    python3 scripts/timer.py mark <note>    # checkpoint, e.g. "end of Phase 1"
    python3 scripts/timer.py status

Events are appended to docs/TIME_LOG.md with the local wall-clock time and
the active minutes so far. Elapsed time is recomputed from the log on every
call, so the file is the only state.
"""

import re
import sys
from datetime import datetime
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "docs" / "TIME_LOG.md"
BUDGET_MIN = 240
HEADER = (
    "# Time log\n\n"
    "Written by `scripts/timer.py` when Nick says start time or pause time.\n"
    "Active minutes count only time between a start and the next pause.\n\n"
    "| Event | Local time | Active min | Note |\n"
    "|---|---|---|---|\n"
)
ROW = re.compile(r"^\| (start|pause|mark) \| (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \|")
FMT = "%Y-%m-%d %H:%M:%S"


def read_events():
    """Return the logged events as (kind, datetime) pairs in file order."""
    if not LOG.exists():
        return []
    events = []
    for line in LOG.read_text().splitlines():
        m = ROW.match(line)
        if m:
            events.append((m.group(1), datetime.strptime(m.group(2), FMT)))
    return events


def active_minutes(events, now):
    """Return active minutes and whether the clock is running at ``now``."""
    total = 0.0
    started = None
    for kind, at in events:
        if kind == "start" and started is None:
            started = at
        elif kind == "pause" and started is not None:
            total += (at - started).total_seconds() / 60
            started = None
    if started is not None:
        total += (now - started).total_seconds() / 60
    return total, started is not None


def main(argv):
    """Run one timer command and return the exit code."""
    if not argv or argv[0] not in {"start", "pause", "mark", "status"}:
        print(__doc__)
        return 2
    kind, note = argv[0], " ".join(argv[1:]).replace("|", "/")
    now = datetime.now().replace(microsecond=0)
    events = read_events()
    total, running = active_minutes(events, now)

    if kind == "status":
        state = "running" if running else "paused"
        left = BUDGET_MIN - total
        print(f"{state}, {total:.1f} of {BUDGET_MIN} min used, {left:.1f} left")
        return 0
    if kind == "start" and running:
        print(f"already running, {total:.1f} min used. Nothing logged.")
        return 1
    if kind == "pause" and not running:
        print(f"already paused, {total:.1f} min used. Nothing logged.")
        return 1

    if not LOG.exists():
        LOG.write_text(HEADER)
    with LOG.open("a") as f:
        f.write(f"| {kind} | {now.strftime(FMT)} | {total:.1f} | {note} |\n")
    print(f"{kind} at {now.strftime(FMT)}, {total:.1f} of {BUDGET_MIN} min used")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
