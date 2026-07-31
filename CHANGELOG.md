# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-31

### Added

- Initial open-source release of RepoGraph-Honest MCP Server.
- `index_project` tool: builds a module-qualified project symbol index with
  content-hash based caching.
- `load_project_deps` tool: parses `requirements.txt` and `pyproject.toml` to
  load installed dependency APIs.
- `check_symbol` and `check_api` tools for verifying project symbols and library
  API calls, including typo suggestions.
- `execute_code` sandbox with timeout, optional Unix memory limits, and
  structured error reporting.
- `scan_file` AST-based undefined-call detection.
- `validate_types` lightweight structural checks (None iteration, builtin arg
  counts, non-callable calls, string-method type mismatches).
- `find_dead_code` with entrypoints, test handling, and ignore patterns.
- `find_similar_code` clone detection using sequence similarity.
- `explore_call_graph` with caller/callee exploration based on AST references.
- `search_code` regex search across project source files.
- `choose_tool` natural-language query routing.

### Changed

- Migrated call-graph and file-scan logic from regex to AST for higher accuracy.
- Symbols are now stored with module-qualified names (e.g. `pkg.core.main`).

### Fixed

- Thread-safety issues in `APIKnowledgeBase` and `mcp/tools.py` global state.
- `explore_call_graph` caller matching bug.
- `check_api` fuzzy-match logic returning inconsistent results.
- `StructureExtractor` incorrectly treating classes as functions.
- Project-index cache invalidation now detects file deletions and content changes.

## [0.0.1] - 2026-07

- Pre-release prototype.
