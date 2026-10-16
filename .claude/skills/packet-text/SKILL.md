---
name: packet-text
description: Read a packet HTML file (requirements, migration brief, stakeholder interviews) as plain text, whole or one section, without the embedded font blobs.
---

The packet files in `packet/` each embed about 500KB of base64 fonts. Never
read them raw.

1. Run `python3 scripts/packet_text.py packet/<file>.html` to print the
   whole text, or add `--start "<heading>"` and `--end "<next heading>"` to
   print one section. The last match of `--start` is used, since headings
   also appear in the table of contents.
2. If the start text is not found, print the whole file once, find the
   exact heading, and run it again with that heading.
3. Quote the packet's wording when a requirement is in question, and name
   the file and section it came from.
