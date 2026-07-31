"""
Parse Python source files into ``ParseResult`` objects.

Provides AST-based extraction of functions, classes, variables, imports,
imports and intra-file reference edges with minimal false positives.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional

from tree_sitter import Language, Parser

from repograph_honest.structure.relations import ParseResult, StructEdge


class StructureExtractor:
    """Extract functions, classes, variables, imports and local edges from a Python file."""

    def __init__(self, parser: Optional[Parser] = None):
        if parser is None:
            try:
                from tree_sitter_python import language as tspython_language

                self.parser = Parser(Language(tspython_language()))
            except Exception as exc:  # noqa: BLE001
                raise ImportError(
                    "tree-sitter Python parser is required; install tree-sitter-python."
                ) from exc
        else:
            self.parser = parser

    def parse_file(self, file_path: str | Path) -> ParseResult:
        """Parse *file_path* and return a ``ParseResult``."""
        p = Path(file_path)
        source = p.read_text(encoding="utf-8")
        return self.parse_source(source)

    def parse_source(self, source: str) -> ParseResult:
        """Parse raw source code and return a ``ParseResult``."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # Fallback: return empty result so callers can continue.
            return ParseResult(
                edges=[],
                func_defs={},
                class_defs={},
                var_defs={},
                imports=set(),
            )

        func_defs: dict[str, tuple[int, int]] = {}
        class_defs: dict[str, tuple[int, int]] = {}
        var_defs: dict[str, tuple[int, int]] = {}
        imports: set[str] = set()
        imported_symbols: dict[str, str] = {}
        edges: list[StructEdge] = []

        self._walk(
            tree,
            source,
            scope="",
            func_defs=func_defs,
            class_defs=class_defs,
            var_defs=var_defs,
            imports=imports,
            imported_symbols=imported_symbols,
            edges=edges,
        )

        return ParseResult(
            edges=edges,
            func_defs=func_defs,
            class_defs=class_defs,
            var_defs=var_defs,
            imports=imports,
            imported_symbols=imported_symbols,
            exported_symbols={n for n in func_defs if not n.startswith("_")}
            | {n for n in class_defs if not n.startswith("_")},
        )

    def _walk(
        self,
        node: ast.AST,
        source: str,
        scope: str,
        func_defs: dict[str, tuple[int, int]],
        class_defs: dict[str, tuple[int, int]],
        var_defs: dict[str, tuple[int, int]],
        imports: set[str],
        imported_symbols: dict[str, str],
        edges: list[StructEdge],
    ) -> None:
        """Recursively walk the AST collecting definitions and edges."""
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = self._scoped_name(scope, child.name)
                func_defs[name] = (child.lineno - 1, child.end_lineno - 1)
                self._collect_local_edges(child, name, func_defs, class_defs, var_defs, edges)
                self._walk(
                    child,
                    source,
                    scope=name,
                    func_defs=func_defs,
                    class_defs=class_defs,
                    var_defs=var_defs,
                    imports=imports,
                    imported_symbols=imported_symbols,
                    edges=edges,
                )
            elif isinstance(child, ast.ClassDef):
                name = self._scoped_name(scope, child.name)
                class_defs[name] = (child.lineno - 1, child.end_lineno - 1)
                self._collect_local_edges(child, name, func_defs, class_defs, var_defs, edges)
                self._walk(
                    child,
                    source,
                    scope=name,
                    func_defs=func_defs,
                    class_defs=class_defs,
                    var_defs=var_defs,
                    imports=imports,
                    imported_symbols=imported_symbols,
                    edges=edges,
                )
            elif isinstance(child, ast.Import):
                for alias in child.names:
                    imports.add(alias.name.split(".")[0])
                    asname = alias.asname or alias.name.split(".")[-1]
                    imported_symbols[asname] = alias.name
            elif isinstance(child, ast.ImportFrom):
                module = child.module or ""
                if child.level:
                    imports.add(module.split(".")[0] if module else ".")
                else:
                    imports.add(module.split(".")[0])
                for alias in child.names:
                    asname = alias.asname or alias.name
                    imported_symbols[asname] = f"{module}.{alias.name}" if module else alias.name
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    self._record_var_def(target, scope, var_defs)
            elif isinstance(child, ast.AnnAssign):
                if child.target is not None:
                    self._record_var_def(child.target, scope, var_defs)
            else:
                self._walk(
                    child,
                    source,
                    scope,
                    func_defs=func_defs,
                    class_defs=class_defs,
                    var_defs=var_defs,
                    imports=imports,
                    imported_symbols=imported_symbols,
                    edges=edges,
                )

    def _record_var_def(
        self,
        target: ast.expr,
        scope: str,
        var_defs: dict[str, tuple[int, int]],
    ) -> None:
        if isinstance(target, ast.Name):
            name = self._scoped_name(scope, target.id)
            var_defs[name] = (target.lineno - 1, target.lineno - 1)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._record_var_def(elt, scope, var_defs)

    @staticmethod
    def _scoped_name(scope: str, name: str) -> str:
        return f"{scope}.{name}" if scope else name

    def _collect_local_edges(
        self,
        node: ast.AST,
        context: str,
        func_defs: dict[str, tuple[int, int]],
        class_defs: dict[str, tuple[int, int]],
        var_defs: dict[str, tuple[int, int]],
        edges: list[StructEdge],
    ) -> None:
        """Create edges from references inside *node* to locally defined symbols."""
        local_names = set(func_defs.keys()) | set(class_defs.keys()) | set(var_defs.keys())

        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                if child.id in local_names:
                    edges.append(
                        StructEdge(
                            src_start=child.lineno - 1,
                            src_end=child.lineno - 1,
                            tgt_start=func_defs.get(child.id, (0, 0))[0],
                            tgt_end=func_defs.get(child.id, (0, 0))[1],
                            relation_type="same_scope",
                            name=child.id,
                        )
                    )
            elif isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Load):
                root_name = self._attribute_root(child)
                if root_name and root_name in local_names:
                    edges.append(
                        StructEdge(
                            src_start=child.lineno - 1,
                            src_end=child.lineno - 1,
                            tgt_start=func_defs.get(root_name, (0, 0))[0],
                            tgt_end=func_defs.get(root_name, (0, 0))[1],
                            relation_type="same_scope",
                            name=root_name,
                        )
                    )

    @staticmethod
    def _attribute_root(node: ast.Attribute) -> Optional[str]:
        """Return the leftmost Name of an attribute chain, if any."""
        current: ast.expr = node.value
        while isinstance(current, ast.Attribute):
            current = current.value
        return current.id if isinstance(current, ast.Name) else None

    def scan_file(self, file_path: str | Path) -> list[dict]:
        """Return a list of obvious issues in a single file.

        Kept for backwards compatibility; prefer the AST-based scan in
        ``repograph_honest.mcp.tools`` for richer diagnostics.
        """
        p = Path(file_path)
        res = self.parse_file(p)
        source = p.read_text(encoding="utf-8")

        defined = set(res.func_defs.keys()) | set(res.class_defs.keys()) | set(res.var_defs.keys())
        defined |= res.imports
        defined |= {
            "print", "len", "range", "enumerate", "zip", "map", "filter", "sorted",
            "sum", "min", "max", "abs", "round", "int", "str", "float", "bool",
            "list", "dict", "set", "tuple", "type", "isinstance", "hasattr", "getattr",
            "open", "input", "repr", "vars", "locals", "globals", "dir", "super",
            "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
            "AttributeError",
        }

        issues: list[dict] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return issues

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = self._call_name(node.func)
            if not name:
                continue
            base = name.split(".")[0]
            if base in defined or name in defined:
                continue
            issues.append({"type": "undefined_call", "name": name, "line": node.lineno})

        return issues

    @staticmethod
    def _call_name(node: ast.expr) -> Optional[str]:
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
