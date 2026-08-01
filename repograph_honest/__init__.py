"""RepoGraph-Honest: verify AI-generated code against project structure and installed APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repograph_honest import honest, mcp, sandbox, structure

__version__ = "0.1.0"
__all__ = ["honest", "mcp", "sandbox", "structure"]


def __getattr__(name: str):
    if name in __all__:
        import importlib

        return importlib.import_module(f"repograph_honest.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
