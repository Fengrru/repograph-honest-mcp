"""Print the project version from pyproject.toml (single source of truth).

Usage: python scripts/read-version.py
"""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)
    print(pyproject["project"]["version"])


if __name__ == "__main__":
    main()
