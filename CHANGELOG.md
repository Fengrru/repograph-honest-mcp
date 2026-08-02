# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Project renamed to HonestCode** — the package, CLI, and environment
  variables were renamed for a distinct brand identity (no longer riding on
  the "CodeGraph" family name):
  - PyPI package `repograph-honest-mcp` → **`honestcode`**
  - Python module `repograph_honest` → **`honestcode`**
  - CLI commands `repograph-honest` / `repograph-honest-mcp` →
    **`honestcode`** / **`honestcode-mcp`**
  - Environment variables `REPOGRAPH_*` → **`HONESTCODE_*`**
  - Project binding directory `.repograph/` → **`.honestcode/`**
  - GitHub repository `Fengrru/repograph-honest-mcp` → **`Fengrru/honestcode`**

### Added

- **Persistent call graph (SQLite)** — `graph/graph_store.py` persists the
  project-wide definitions/references graph next to the symbol index, keyed by
  content hashes of every source file. `explore_call_graph` and
  `find_dead_code` now read from disk instead of re-parsing on every call:
  measured **~1 ms** hot (was ~285 ms / ~340 ms). First call after a change
  pays a cold rebuild (~278 ms on this repo).
- **FTS5 full-text search** — `search_code` narrows plain-`*.py` regex scans
  to candidate files via a FTS5 virtual table, keeping results identical
  (superset candidate set) while touching far fewer files on large repos.
- **`explore_impact` tool** — blast radius of a symbol: transitively impacted
  symbols/files via bidirectional call-graph BFS; `explore_call_graph` now
  also returns an `impact` summary.
- **`affected_files` tool** — trace a `git diff` through the call graph to
  find affected files and tests (CI-friendly).
- **File watcher** — zero-dependency polling watcher (`graph/watcher.py`)
  with debounce; `index_project(watch=True)`, CLI `watch` subcommand, and
  `stop_watching` tool keep the index fresh automatically.
- **Project binding & client install** — `honestcode init` /
  `uninit` / `install` / `root`: `.honestcode/` binding directory plus
  auto-configuration of Cursor, VS Code and Claude Code MCP configs.
- **Multi-language support (optional)** — `honestcode[multi-language]`
  extras with tree-sitter symbol extraction for JS/TS/Go/Rust/Java;
  `scan_file` handles non-Python files when installed, and degrades with a
  clear message otherwise.
- **External-repo benchmarks** — `scripts/benchmark.py` gains `--repo`,
  `--repos`, `--format markdown|json`, and cold-vs-hot graph timings.
- **CLI** (`honestcode` command) with a 1:1 subcommand for every MCP
  tool: `index`, `deps`, `scan`, `check-symbol`, `check-api`, `validate`,
  `execute`, `dead-code`, `similar`, `call-graph`, `impact`, `affected`,
  `search`, `load-package`, `stats`, `choose-tool`, `init`, `uninit`,
  `install`, `root`, `watch`. Output is JSON; exit codes are non-zero when
  issues are found so the CLI drops into CI pipelines cleanly.
- **`HONESTCODE_TOOLS` environment variable** now actually controls which
  tools the MCP server exposes. Defaults to `scan_file`; accepts a
  comma-separated list or `all`. Unknown names are ignored with a warning.
- **SSE transport** for the MCP server (`honestcode-mcp --transport
  sse --host 0.0.0.0 --port 8000`), matching the CHANGELOG claim.
- False-positive regression tests: `scan_file` verified to stay silent on
  all builtins (any/all/frozenset/id/hash/ord/chr/pow/...), `self.method()`,
  `from X import Y`, relative imports, `import X as Y`, walrus assignments,
  loop variables, nested functions, dataclasses, and complex call targets.
- `explore_call_graph` callees tests (previously untested and broken).

### Fixed

- **`scan_file` false positives** — the defined-symbol set now includes:
  parameters and `self`/`cls` (so `self.helper()` is not flagged), every
  name introduced by `from X import Y` / `import X as Y` (so relative and
  aliased imports resolve), loop targets and walrus assignments, and the
  **full `builtins` module** instead of a hand-picked 40-name subset.
- **`explore_call_graph` callees** — reference contexts are now recorded as
  module-qualified names (e.g. `pkg.core.main`) instead of short names
  (`main`), so querying `pkg.core.main` actually returns its callees.
  Class method callees (`pkg.core.Worker.work`) also resolve correctly.
- **`check_api` dead branch** — the `unknown module` case had two
  identical return paths; collapsed into one and added an empty
  `suggestion` list for API consistency.
- **`StructureExtractor`** no longer hard-requires `tree-sitter-python` at
  construction time. The parser has always used `ast`; the tree-sitter
  import was a vestigial guard that raised a misleading `ImportError`.

### Changed

- Dropped `tree-sitter` and `tree-sitter-python` runtime dependencies —
  the extractor parses with the standard-library `ast` module, so there
  is no native parser to install. `tree-sitter` remains on the roadmap for
  future multi-language support.
- `[project.scripts]` now declares two entry points:
  `honestcode-mcp` (MCP server) and `honestcode` (CLI).
- README architecture diagram and module layout updated to reflect the
  `ast`-based extractor and the new `cli.py` module.

## [0.1.0] - 2026-07-31

### Added

- Initial open-source release of HonestCode MCP Server.
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
- Content-hash based index caching in `~/.cache/honestcode/`.
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
