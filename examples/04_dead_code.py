"""Example: find potentially unused symbols in a project."""

from __future__ import annotations

import sys

from repograph_honest.mcp.tools import find_dead_code, index_project


def main(project_root: str) -> None:
    index_project(project_root, force_rebuild=True)
    result = find_dead_code(entrypoints=["pkg.cli.main"])
    print("find_dead_code:", result)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    main(root)
