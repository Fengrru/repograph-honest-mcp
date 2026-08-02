"""Promote the [Unreleased] section of CHANGELOG.md into a named version.

Mirrors CodeGraph's `prepare-release.mjs`: idempotent — if the version block
already exists, or [Unreleased] is empty, the file is left untouched.

Usage: python scripts/prepare-release.py <version>
Exits 0 if the file changed, 1 if nothing to do (so CI can decide to commit).
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"

HEADING = re.compile(r"^## \[(?P<name>[^\]]+)\](?P<rest>[^\n]*)$", re.MULTILINE)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <version>", file=sys.stderr)
        return 2

    version = sys.argv[1]
    text = CHANGELOG.read_text(encoding="utf-8")

    # Locate the [Unreleased] heading.
    match = None
    for m in HEADING.finditer(text):
        if m.group("name").strip().lower() == "unreleased":
            match = m
            break
    if match is None:
        print("no [Unreleased] section found; nothing to do", file=sys.stderr)
        return 1

    # If the target version block already exists, bail out (idempotent).
    if any(
        m.group("name").strip() == version
        for m in HEADING.finditer(text)
        if m.start() > match.start()
    ):
        print(f"CHANGELOG already contains [{version}]; nothing to do")
        return 1

    # Ensure the [Unreleased] block actually has content beneath it.
    rest = text[match.end() :]
    next_heading = HEADING.search(rest)
    block = rest if next_heading is None else rest[: next_heading.start()]
    if not block.strip():
        print("[Unreleased] is empty; nothing to promote")
        return 1

    new_heading = f"## [{version}] - {date.today().isoformat()}"
    new_text = text[: match.start()] + new_heading + text[match.end() :]
    CHANGELOG.write_text(new_text, encoding="utf-8")
    print(f"promoted [Unreleased] -> [{version}] in {CHANGELOG.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
