"""
RepoGraph-Honest MCP Server.

A Model Context Protocol server that exposes hallucination-detection tools
so any MCP-compatible client (Cursor, Claude Desktop, VS Code, etc.) can
verify generated code against the real project structure and dependencies.

Run with:
    python -m repograph_honest.mcp.server
"""

from __future__ import annotations

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("repograph_honest.mcp")

mcp = FastMCP("repograph-honest")


@mcp.tool()
def mcp_index_project(root_path: str, force_rebuild: bool = False) -> dict:
    """Build (or reuse) the symbol index for a project directory.

    Call this once before other tools. Subsequent calls return a cached index
    unless force_rebuild=True.

    Args:
        root_path: Absolute path to the project root.
        force_rebuild: If True, discard the cache and rebuild the index.
    """
    logger.info("index_project(%s, force_rebuild=%s)", root_path, force_rebuild)
    return index_project(root_path, force_rebuild=force_rebuild)


@mcp.tool()
def mcp_load_project_deps(root_path: str) -> dict:
    """Load dependency APIs declared in requirements.txt / pyproject.toml
    so library calls can be validated.

    Args:
        root_path: Absolute path to the project root.
    """
    return load_project_deps(root_path)


@mcp.tool()
def mcp_check_symbol(symbol_name: str, file_path: str = "") -> dict:
    """Check whether a symbol is actually defined in the project.

    Args:
        symbol_name: The identifier to verify (function/class/variable name).
        file_path: Optional file the symbol appears in.
    """
    return check_symbol(symbol_name, file_path or None)


@mcp.tool()
def mcp_check_api(api_name: str) -> dict:
    """Verify a library API call is correct, e.g. pd.read_exel → read_excel.

    Args:
        api_name: Fully qualified API name, e.g. "pandas.read_csv".
    """
    return check_api(api_name)


@mcp.tool()
def mcp_execute_code(
    code: str, prelude: str = "", known_names: Optional[list[str]] = None
) -> dict:
    """Execute code in a sandbox and return stdout/stderr plus structured
    error analysis with fix suggestions.

    Args:
        code: Python source to execute.
        prelude: Optional setup code (imports) run before `code`.
        known_names: Optional list of known symbol names for typo suggestions.
    """
    return execute_code(code, prelude, known_names)


@mcp.tool()
def mcp_scan_file(file_path: str) -> dict:
    """Scan a file for potential hallucinations: undefined symbols, missing
    imports, and incorrect API calls.

    Args:
        file_path: Absolute path to the Python file.
    """
    return scan_file(file_path)


@mcp.tool()
def mcp_load_package_apis(package_name: str) -> dict:
    """Load (and cache) API signatures for a specific installed package.

    Args:
        package_name: Importable package name, e.g. "numpy".
    """
    return load_package_apis(package_name)


@mcp.tool()
def mcp_get_project_stats() -> dict:
    """Return statistics about the currently indexed project."""
    return get_project_stats()


@mcp.tool()
def mcp_validate_types(code: str) -> dict:
    """Run a lightweight AST-based structural check on code.

    Args:
        code: Python source to analyze.
    """
    return validate_types(code)


@mcp.tool()
def mcp_find_dead_code(
    entrypoints: Optional[list[str]] = None,
    ignore_patterns: Optional[list[str]] = None,
    include_tests: bool = True,
) -> dict:
    """Find symbols that appear to be unused in the indexed project.

    Args:
        entrypoints: Symbol names to always treat as alive (e.g. ["main", "cli"]).
        ignore_patterns: Regex patterns for files to exclude from dead-code results.
        include_tests: Treat symbols in test files as alive.
    """
    return find_dead_code(entrypoints, ignore_patterns, include_tests)


@mcp.tool()
def mcp_find_similar_code(threshold: float = 0.85) -> dict:
    """Find function-level code clones across the project.

    Args:
        threshold: Similarity ratio above which two functions are reported (0-1).
    """
    return find_similar_code(threshold)


@mcp.tool()
def mcp_explore_call_graph(symbol_name: str) -> dict:
    """Explore callers and callees of a symbol across the project.

    Args:
        symbol_name: Name of the symbol to explore.
    """
    return explore_call_graph(symbol_name)


@mcp.tool()
def mcp_search_code(pattern: str, glob: str = "*.py") -> dict:
    """Search project source code with a regex pattern.

    Args:
        pattern: Regular expression to search for.
        glob: Glob pattern for files to search.
    """
    return search_code(pattern, glob)


@mcp.tool()
def mcp_choose_tool(query: str) -> dict:
    """For debugging: choose which tool a natural-language query maps to."""
    return choose_tool(query)


def main():
    logger.info("Starting RepoGraph-Honest MCP server (stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
