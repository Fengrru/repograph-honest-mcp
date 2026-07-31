"""Example: index a project and check whether a symbol is defined."""

from __future__ import annotations

import sys

from repograph_honest.mcp.tools import check_symbol, index_project


def main(project_root: str) -> None:
    idx = index_project(project_root)
    print("index_project:", idx)

    # Try a likely module-qualified symbol; adjust for your project.
    result = check_symbol("pkg.core.main")
    print("check_symbol:", result)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    main(root)
