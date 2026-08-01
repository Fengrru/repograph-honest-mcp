<div align="center">

# RepoGraph-Honest MCP Server

**Catch AI code hallucinations before they reach your editor.**

[![CI](https://github.com/Fengrru/repograph-honest-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Fengrru/repograph-honest-mcp/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/repograph-honest-mcp)](https://pypi.org/project/repograph-honest-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/repograph-honest-mcp)](https://pypi.org/project/repograph-honest-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/repograph-honest-mcp)](https://pypi.org/project/repograph-honest-mcp/)

A lightweight [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that verifies
AI-generated code against your actual project structure and installed dependencies — detecting
undefined symbols, wrong API calls, dead code, and type mismatches in real time.

</div>

---

## Why RepoGraph-Honest?

AI coding assistants are powerful but unreliable. They hallucinate function names, invent library
APIs, and produce dead code. **RepoGraph-Honest** acts as a verification layer between the model
and your editor:

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  AI Model   │────▶│  RepoGraph-Honest │────▶│   Editor    │
│  generates  │     │  verifies code    │     │  receives   │
│  code       │     │  against project  │     │  clean code │
└─────────────┘     └──────────────────┘     └─────────────┘
```

- **No heavyweight ML** — pure Python AST analysis, no `torch`/`transformers`
- **MCP-native** — works with Cursor, Claude Desktop, VS Code, and any MCP client
- **Fast & cached** — content-hash invalidation, thread-safe global state
- **14 built-in tools** — from symbol checks to call graph exploration

---

## Features

| Category | Tool | Description |
|:---------|:-----|:------------|
| **Indexing** | `index_project` | Build a module-qualified symbol index with content-hash caching |
| | `load_project_deps` | Parse `requirements.txt` / `pyproject.toml` and load dependency APIs |
| | `load_package_apis` | Load API signatures for a single package |
| | `get_project_stats` | Get index statistics |
| **Verification** | `check_symbol` | Verify an identifier is defined in the project |
| | `check_api` | Verify a library API call exists (with typo suggestions) |
| | `validate_types` | Structural checks: None iteration, wrong arg counts, etc. |
| | `scan_file` | Scan a file for all undefined calls via AST analysis |
| **Analysis** | `explore_call_graph` | Explore callers and callees of a symbol |
| | `find_dead_code` | Find unused symbols with entrypoint support |
| | `find_similar_code` | Detect code clones via sequence similarity |
| | `search_code` | Regex search across project source files |
| **Execution** | `execute_code` | Run code in a sandboxed subprocess with timeout |
| **Routing** | `choose_tool` | Map natural language queries to the best tool |

---

## Quick Start

### 1. Install

```bash
pip install repograph-honest-mcp
```

Or from source:

```bash
git clone https://github.com/Fengrru/repograph-honest-mcp.git
cd repograph-honest-mcp
pip install -e .
```

> **Requires** Python >= 3.10

### 2. Configure your MCP client

Add to your client's MCP configuration (e.g. `~/.cursor/mcp.json` for Cursor):

```json
{
  "mcpServers": {
    "repograph-honest": {
      "command": "repograph-honest-mcp"
    }
  }
}
```

Or run directly with Python:

```json
{
  "mcpServers": {
    "repograph-honest": {
      "command": "python",
      "args": ["-m", "repograph_honest.mcp.server"]
    }
  }
}
```

### 3. Use it

After restarting your MCP client, the tools are available. A typical workflow:

```
1. Index your project      →  index_project("/path/to/project")
2. Load dependency APIs    →  load_project_deps("/path/to/project")
3. Verify generated code   →  check_symbol("pkg.core.helper")
                             check_api("pandas.read_csv")
                             scan_file("generated.py")
                             execute_code("print(1 + 1)")
```

---

## Tool Reference

<details>
<summary><strong><code>index_project(root_path, force_rebuild=False)</code></strong></summary>

Build or reuse the project symbol index. Returns indexed symbol count, root path, and cache status.

```python
index_project("/path/to/project")
# {"success": true, "symbols_indexed": 42, "root": "/path/to/project", "cached": false}
```

</details>

<details>
<summary><strong><code>load_project_deps(root_path)</code></strong></summary>

Parse `requirements.txt` or `pyproject.toml` and load public API signatures of installed packages.

```python
load_project_deps("/path/to/project")
# {"success": true, "packages_loaded": ["requests", "pytest"], "total_apis": 1204}
```

</details>

<details>
<summary><strong><code>check_symbol(symbol_name, file_path=None)</code></strong></summary>

Verify a symbol is defined in the indexed project. Symbols use module-qualified names (`pkg.core.main`).

```python
check_symbol("pkg.core.main")
# {"success": true, "symbol": "pkg.core.main", "defined": true, "location": {...}}
```

</details>

<details>
<summary><strong><code>check_api(api_name)</code></strong></summary>

Check if a library API exists. Returns fuzzy suggestions for typos.

```python
check_api("math.sqrt")    # valid
check_api("math.sqrtt")   # invalid → suggests "math.sqrt"
```

</details>

<details>
<summary><strong><code>execute_code(code, prelude="", known_names=None)</code></strong></summary>

Run code in a sandboxed subprocess with timeout and temp working directory.

```python
execute_code("print(1 + 1)")
# {"success": true, "output": "2", ...}
```

</details>

<details>
<summary><strong><code>scan_file(file_path)</code></strong></summary>

AST-based scan for undefined calls in a file.

```python
scan_file("/path/to/project/bad.py")
# {"success": true, "issues": [{"type": "undefined_call", "name": "...", "line": 7}]}
```

</details>

<details>
<summary><strong><code>validate_types(code)</code></strong></summary>

Lightweight structural checks on code snippets:
- Iterating over `None`
- Wrong argument counts for common builtins (`len`, `sum`, etc.)
- Calling constant values
- String methods on non-string constants

```python
validate_types("for x in None:\n    pass")
# {"success": true, "issues": [{"type": "none_iteration", ...}]}
```

</details>

<details>
<summary><strong><code>find_dead_code(entrypoints, ignore_patterns, include_tests=True)</code></strong></summary>

Find unused symbols. Provide entrypoints to keep known roots alive.

```python
find_dead_code(entrypoints=["pkg.cli.main"])
# {"success": true, "dead_symbols": [...], "count": 3}
```

</details>

<details>
<summary><strong><code>find_similar_code(threshold=0.6)</code></strong></summary>

Detect function-level code clones across the project.

</details>

<details>
<summary><strong><code>explore_call_graph(symbol_name)</code></strong></summary>

Return definitions, callers, and callees of a symbol.

```python
explore_call_graph("pkg.core.helper")
# {"success": true, "callers": [...], "callees": [...]}
```

</details>

<details>
<summary><strong><code>search_code(pattern, glob="*.py")</code></strong></summary>

Regex search across project source files.

```python
search_code(r"def \w+_helper")
```

</details>

<details>
<summary><strong><code>choose_tool(query)</code></strong></summary>

Map a natural-language query to the best tool for the job.

</details>

---

## Architecture

```
repograph_honest/
├── mcp/                    # MCP server layer
│   ├── server.py           # FastMCP entry point (stdio/SSE)
│   ├── tools.py            # 14 tool implementations
│   └── knowledge_base.py   # Dependency API signature cache
├── honest/                 # Core hallucination detection
│   ├── router.py           # NL query → tool routing
│   └── symbol_index.py     # Project-wide symbol index + caching
├── structure/              # Code structure extraction
│   ├── extractor.py        # AST-based parser
│   └── relations.py        # Edge/relation data structures
└── sandbox/                # Sandboxed execution
    └── __init__.py         # Subprocess executor with timeout
```

### Key Design Decisions

| Decision | Rationale |
|:---------|:----------|
| **AST-first** | Call graphs and file scans use `ast` instead of fragile regex |
| **Module-qualified symbols** | Index stores `pkg.module.func` so cross-file references are unambiguous |
| **Lazy loading + caching** | Dependency APIs and project indices are cached with content-hash invalidation |
| **Thread-safe global state** | Tool state protected by `RLock` for concurrent MCP requests |
| **Subprocess sandbox** | `execute_code` runs in isolation with timeout and optional memory limits |

---

## Development

```bash
# Clone and install
git clone https://github.com/Fengrru/repograph-honest-mcp.git
cd repograph-honest-mcp
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run tests
pytest

# Lint & format
ruff check repograph_honest tests scripts
ruff format repograph_honest tests scripts

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request guidelines.

---

## Security

`execute_code` runs in a subprocess with timeout protection and a temporary working directory.
It catches accidental mistakes but is **not** a hardened security boundary. For untrusted code,
use a container or dedicated VM.

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

---

## Roadmap

- [ ] TypeScript/JavaScript project support via tree-sitter
- [ ] VS Code extension with inline diagnostics
- [ ] GitHub Action for PR-level hallucination checks
- [ ] Remote dependency API caching (PyPI index)
- [ ] Configurable rules and ignore patterns

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

---

## License

[MIT](LICENSE) - Copyright (c) 2026 RepoGraph-Honest Team
