"""Optional tree-sitter multi-language symbol extraction.

Python remains the fully supported language (stdlib ``ast``). For JavaScript,
TypeScript and a few other popular languages, symbol extraction is available
when the optional extras are installed::

    pip install -e "honestcode[multi-language]"

Everything degrades gracefully: without tree-sitter, ``is_supported`` still
recognizes the file by extension, but ``extract_symbols`` raises
``TreeSitterUnavailable`` so callers can report a clear message instead of a
traceback.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LANG_BY_EXT: dict[str, str] = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
}

# node type -> symbol kind, per language (tree-sitter grammar node names).
_SYMBOL_RULES: dict[str, list[tuple[str, str]]] = {
    "javascript": [
        ("function_declaration", "function"),
        ("class_declaration", "class"),
        ("method_definition", "method"),
        ("function_expression", "function"),
    ],
    "typescript": [
        ("function_declaration", "function"),
        ("class_declaration", "class"),
        ("method_definition", "method"),
        ("function_expression", "function"),
        ("interface_declaration", "interface"),
        ("type_alias_declaration", "type"),
        ("enum_declaration", "enum"),
    ],
    "go": [
        ("function_declaration", "function"),
        ("method_declaration", "method"),
        ("type_declaration", "type"),
        ("type_spec", "type"),
    ],
    "rust": [
        ("function_item", "function"),
        ("struct_item", "struct"),
        ("enum_item", "enum"),
        ("trait_item", "trait"),
        ("impl_item", "impl"),
    ],
    "java": [
        ("class_declaration", "class"),
        ("interface_declaration", "interface"),
        ("enum_declaration", "enum"),
        ("method_declaration", "method"),
    ],
}

_QUERIES: dict[str, object] = {}


class TreeSitterUnavailable(RuntimeError):
    """Raised when tree-sitter (or a language grammar) is not installed."""


def detect_language(path: str | Path) -> str | None:
    """Return the language name for *path* by extension, or None."""
    return LANG_BY_EXT.get(Path(path).suffix.lower())


def is_supported(path: str | Path) -> bool:
    return detect_language(path) is not None


def _import_tree_sitter():  # pragma: no cover - requires optional extras
    try:
        from tree_sitter import Language, Parser  # noqa: F401

        return Language, Parser
    except ImportError as exc:
        raise TreeSitterUnavailable(
            "tree-sitter is not installed. Run: pip install -e '.[multi-language]'"
        ) from exc


def _load_language(name: str) -> object:  # pragma: no cover - requires optional extras
    """Load a language grammar, supporting tree-sitter >= 0.21 binding APIs."""
    try:
        module = importlib.import_module(f"tree_sitter_{name}")
    except ImportError as exc:
        raise TreeSitterUnavailable(
            f"Grammar for '{name}' not installed (tree-sitter-{name} package)"
        ) from exc

    factory = getattr(module, "language", None)
    if factory is None:  # old-style bindings
        raise TreeSitterUnavailable(f"Unsupported tree-sitter-{name} binding (no language())")
    lang = factory()
    # tree-sitter >= 0.22 returns a Language instance; 0.21 returns a handle.
    try:
        from tree_sitter import Language

        if not isinstance(lang, Language):
            lang = Language(lang)
    except Exception:  # noqa: BLE001
        pass
    return lang


def _query_for(name: str, Language) -> object:  # pragma: no cover - requires optional extras
    if name in _QUERIES:
        return _QUERIES[name]
    parts = [f"({node} name: (identifier) @name.{kind})" for node, kind in _SYMBOL_RULES[name]]
    query = Language.query(" ".join(parts))
    _QUERIES[name] = query
    return query


def extract_symbols(path: str | Path) -> list[dict]:  # pragma: no cover - requires optional extras
    """Extract ``{name, line, kind}`` symbols from a non-Python source file.

    Raises ``TreeSitterUnavailable`` when the optional dependency is missing.
    """
    path = Path(path)
    lang = detect_language(path)
    if lang is None:
        raise ValueError(f"Unsupported language for {path}")

    Language, Parser = _import_tree_sitter()
    grammar = _load_language(lang)
    parser = Parser()
    parser.language = grammar
    source = path.read_bytes()

    tree = parser.parse(source)
    query = _query_for(lang, Language)
    captures = query.captures(tree.root_node)

    symbols: list[dict] = []
    for node, tag in captures:
        tag = str(tag)
        if not tag.startswith("name."):
            continue
        name = node.text.decode("utf-8", errors="replace")
        if not name:
            continue
        symbols.append(
            {
                "name": name,
                "line": node.start_point[0] + 1,
                "kind": tag.split(".", 1)[1],
            }
        )
    return symbols
