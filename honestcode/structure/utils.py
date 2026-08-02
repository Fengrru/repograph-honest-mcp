"""Shared AST utilities for HonestCode."""

from __future__ import annotations

import ast

__all__ = ["call_name", "call_base"]


def call_name(node: ast.expr) -> str | None:
    """Return a dotted name for a call target (e.g. ``obj.method``).

    Returns ``None`` for complex expressions (e.g. ``(a + b).foo()``).
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
    return None


def call_base(name: str) -> str:
    """Return the first component of a dotted name."""
    return name.split(".")[0]
