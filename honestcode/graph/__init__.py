"""Persistent graph storage for HonestCode.

The call graph (definitions + references) is expensive to rebuild — it needs
an AST pass over every source file. ``graph_store.GraphCache`` persists it to
SQLite next to the symbol index so graph queries read from disk instead of
re-parsing the project on every call, and a FTS5 virtual table backs fast
full-text search.
"""

from honestcode.graph.graph_store import CallGraph, GraphCache
from honestcode.graph.watcher import ProjectWatcher

__all__ = ["CallGraph", "GraphCache", "ProjectWatcher"]
