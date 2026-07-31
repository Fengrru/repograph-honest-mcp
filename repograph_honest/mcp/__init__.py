"""MCP server integration for RepoGraph-Honest."""

from repograph_honest.mcp.knowledge_base import APIKnowledgeBase, APISignature
from repograph_honest.mcp.server import main, mcp
from repograph_honest.mcp.tools import (
    check_api,
    check_symbol,
    choose_tool,
    execute_code,
    explore_call_graph,
    find_dead_code,
    find_similar_code,
    get_project_stats,
    index_project,
    load_package_apis,
    load_project_deps,
    scan_file,
    search_code,
    validate_types,
)

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
