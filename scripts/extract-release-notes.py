"""Extract a version's release notes from CHANGELOG.md for the GitHub Release.

Usage: python scripts/extract-release-notes.py <version> [> notes.md]
Falls back to [Unreleased] when the requested version block is missing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"

HEADING = re.compile(r"^## \[(?P<name>[^\]]+)\](?P<rest>[^\n]*)$", re.MULTILINE)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <version>", file=sys.stderr)
        return 2

    requested = sys.argv[1]
    text = CHANGELOG.read_text(encoding="utf-8")
    headings = list(HEADING.finditer(text))

    def block_for(name: str) -> str | None:
        for i, m in enumerate(headings):
            if m.group("name").strip().lower() != name.lower():
                continue
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            return text[m.end() : end].strip()
        return None

    notes = block_for(requested) or block_for("Unreleased")
    if notes is None:
        print(f"no release notes found for [{requested}]", file=sys.stderr)
        return 1
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
