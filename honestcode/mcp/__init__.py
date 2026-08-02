"""MCP server integration for HonestCode.

Import directly from submodules to avoid loading the MCP server eagerly:

    from honestcode.mcp.tools import scan_file
    from honestcode.mcp.server import main
"""

from __future__ import annotations

__all__ = [
    "APIKnowledgeBase",
    "APISignature",
    "check_api",
    "check_symbol",
    "choose_tool",
    "execute_code",
    "explore_call_graph",
    "find_dead_code",
    "find_similar_code",
    "get_project_stats",
    "index_project",
    "load_package_apis",
    "load_project_deps",
    "main",
    "mcp",
    "scan_file",
    "search_code",
    "validate_types",
]


def __getattr__(name: str):
    if name in ("main", "mcp"):
        from honestcode.mcp.server import main, mcp

        return {"main": main, "mcp": mcp}[name]
    if name in ("APIKnowledgeBase", "APISignature"):
        from honestcode.mcp.knowledge_base import APIKnowledgeBase, APISignature

        return {"APIKnowledgeBase": APIKnowledgeBase, "APISignature": APISignature}[name]
    if name in __all__:
        from honestcode.mcp import tools

        return getattr(tools, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
