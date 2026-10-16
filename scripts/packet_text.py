r"""Print the readable text of a packet HTML file.

Each packet file embeds about 500KB of base64 fonts, so reading the raw HTML
wastes context. This drops ``<style>``, ``<script>`` and ``data:`` blobs and
the tags, and prints one line per text block.

Example::

    python3 scripts/packet_text.py packet/Take_Home_Packet.html \
        --start "Part B: Stakeholder backlog" --end "Part C: One AI feature"
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path


def packet_text(raw: str) -> str:
    """Return the visible text of ``raw`` HTML, one block per line."""
    text = re.sub(r"<(style|script)\b.*?</\1>", "", raw, flags=re.S | re.I)
    text = re.sub(r"data:[^\"')]+", "", text)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()


def section(text: str, start: str | None, end: str | None) -> str:
    """Return ``text`` from the last ``start`` up to the next ``end``.

    The last match is used because a heading also appears in the page's
    table of contents. A missing ``start`` exits with an error.
    """
    if start:
        at = text.rfind(start)
        if at < 0:
            sys.exit(f"start text not found: {start!r}")
        text = text[at:]
    if end:
        stop = text.find(end, 1)
        if stop > 0:
            text = text[:stop]
    return text


def main() -> None:
    """Parse arguments and print the text."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path)
    parser.add_argument("--start", help="print from the last occurrence of this")
    parser.add_argument("--end", help="stop at the next occurrence of this")
    args = parser.parse_args()
    text = packet_text(args.file.read_text(encoding="utf-8"))
    print(section(text, args.start, args.end))


if __name__ == "__main__":
    main()
