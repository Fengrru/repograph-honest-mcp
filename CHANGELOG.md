# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Professional README with architecture diagrams and expandable tool reference.
- PyPI publish workflow (`publish.yml`).
- Dependabot configuration for automated dependency updates.
- GitHub issue templates (bug report, feature request) and PR template.
- Coverage reporting via Codecov in CI.
- Additional ruff lint rules (B, UP, SIM, TCH).

### Changed

- Enhanced CI matrix to include Python 3.13.
- Improved `pyproject.toml` with more classifiers and project URLs.
- Updated `CONTRIBUTING.md` with detailed development setup and PR guidelines.

## [0.1.0] - 2026-07-31

### Added

- Initial open-source release of RepoGraph-Honest MCP Server.
- **Indexing tools**: `index_project`, `load_project_deps`, `load_package_apis`, `get_project_stats`
  - Build module-qualified project symbol indices with content-hash caching.
  - Parse `requirements.txt` and `pyproject.toml` to load dependency API signatures.
- **Verification tools**: `check_symbol`, `check_api`, `validate_types`, `scan_file`
  - Verify identifiers are defined in the project.
  - Verify library API calls exist with typo suggestions via `difflib`.
  - Structural type checks: None iteration, wrong argument counts, non-callable calls.
  - AST-based undefined-call detection across entire files.
- **Analysis tools**: `explore_call_graph`, `find_dead_code`, `find_similar_code`, `search_code`
  - Explore callers and callees of any symbol.
  - Detect unused symbols with entrypoint support and ignore patterns.
  - Find function-level code clones via sequence similarity.
  - Regex search across project source files.
- **Execution**: `execute_code` sandboxed subprocess with timeout and optional POSIX memory limits.
- **Routing**: `choose_tool` natural-language query to tool mapping.
- MCP server with `stdio` and `SSE` transport support.
- Thread-safe global state protected by `RLock`.
- Content-hash based index caching in `~/.cache/repograph_honest/`.
- SQLite serialization support for project indices.
- 4 example scripts demonstrating library usage.
- CI pipeline on GitHub Actions (3 OS x 3 Python versions).
- Pre-commit hooks with ruff linting and formatting.

### Fixed

- Thread-safety issues in `APIKnowledgeBase` and `mcp/tools.py` global state.
- `explore_call_graph` caller matching bug.
- `check_api` fuzzy-match logic returning inconsistent results.
- `StructureExtractor` incorrectly treating classes as functions.
- Project-index cache invalidation now detects file deletions and content changes.

## [0.0.1] - 2026-07

- Pre-release prototype.
