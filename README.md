# RepoGraph-Honest MCP Server

[![CI](https://github.com/Fengrru/repograph-honest-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Fengrru/repograph-honest-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

> A lightweight [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that catches code
> hallucinations in real time — undefined symbols, wrong library API calls, dead code,
> and obvious type mismatches — by verifying generated code against your project structure
> and installed dependencies.

RepoGraph-Honest is a self-contained extraction of the "honest action routing" idea.
Instead of trusting a code model blindly, it **checks** the symbols and APIs the model
emits before they reach your editor.

It is **not** a heavyweight ML system: it needs only `mcp`, `tree-sitter`, and
`tree-sitter-python` — no `torch` / `transformers`.

---

## Table of contents

- [Features](#features)
- [Installation](#installation)
- [Running the server](#running-the-server)
- [Connecting to an MCP client](#connecting-to-an-mcp-client)
- [Tool reference](#tool-reference)
- [Typical workflow](#typical-workflow)
- [Architecture](#architecture)
- [Development](#development)
- [Sandbox security](#sandbox-security)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| Capability | Tool | What it does |
|------------|------|--------------|
| Project indexing | `index_project` | Builds a symbol index (functions / classes / variables) from a directory; caches results across calls |
| Dependency APIs | `load_project_deps` | Loads public API signatures from `requirements.txt` / `pyproject.toml` |
| Symbol check | `check_symbol` | Verifies an identifier is defined in the project |
| API check | `check_api` | Verifies a library API call is correct (e.g. `pd.read_exel` → suggestions) |
| Sandbox exec | `execute_code` | Runs code in a subprocess sandbox; returns stdout/stderr + error type |
| File scan | `scan_file` | Scans a whole file for undefined calls |
| Package APIs | `load_package_apis` | Loads/caches API signatures for one package |
| Stats | `get_project_stats` | Index statistics |
| Type check | `validate_types` | Lightweight AST-based structural checks (None iteration, wrong arg counts, etc.) |
| Dead code | `find_dead_code` | Finds symbols that appear unused; supports entrypoints and ignore patterns |
| Similar code | `find_similar_code` | Finds function-level code clones across the project |
| Call graph | `explore_call_graph` | Explores callers and callees of a symbol |
| Search | `search_code` | Regex search across project source files |
| Tool routing | `choose_tool` | Maps a natural-language query to the best tool |

---

## Installation

```bash
# from source
git clone https://github.com/Fengrru/repograph-honest-mcp.git
cd repograph-honest-mcp
pip install -e .

# or just the runtime deps
pip install -r requirements.txt
```

Python ≥ 3.10 is required.

---

## Running the server

```bash
# as a module (stdio transport — what MCP clients expect)
python -m repograph_honest.mcp.server

# via the launcher script
python scripts/run_mcp_server.py

# HTTP/SSE transport (optional)
python scripts/run_mcp_server.py --transport sse --host 127.0.0.1 --port 8000
```

---

## Connecting to an MCP client

Add this to your client's MCP configuration (Cursor, Claude Desktop, VS Code, etc.):

```json
{
  "mcpServers": {
    "repograph-honest": {
      "command": "python",
      "args": ["-m", "repograph_honest.mcp.server"],
      "cwd": "/absolute/path/to/repograph-honest-mcp"
    }
  }
}
```

After restarting the client, the tools above become available.

---

## Tool reference

All tools are exposed by the MCP server. They can also be called directly from Python
(see [`examples/`](examples/)).

### `index_project(root_path: str, force_rebuild: bool = False) -> dict`

Build (or reuse) the project symbol index.

```python
index_project("/path/to/project")
# => {"success": True, "symbols_indexed": 42, "root": "...", "cached": False}
```

### `load_project_deps(root_path: str) -> dict`

Parse `requirements.txt` or `pyproject.toml` and load the public API signatures of
listed packages.

```python
load_project_deps("/path/to/project")
# => {"success": True, "packages_loaded": ["requests", "pytest"], "total_apis": 1204}
```

### `check_symbol(symbol_name: str, file_path: str | None = None) -> dict`

Check whether a symbol is defined in the indexed project.

Symbols are stored with their full module-qualified name, e.g. `pkg.core.main`.

```python
check_symbol("pkg.core.main")
# => {"success": True, "symbol": "pkg.core.main", "defined": True, "location": {...}}
```

### `check_api(api_name: str) -> dict`

Check whether a library API exists and get suggestions for typos.

```python
check_api("math.sqrt")   # valid
check_api("math.sqrtt")  # invalid + suggestions
```

### `execute_code(code: str, prelude: str = "", known_names: list[str] | None = None) -> dict`

Run code in a fresh subprocess with a temporary working directory and timeout.

```python
execute_code("print(1 + 1)")
# => {"success": True, "output": "2", ...}
```

### `scan_file(file_path: str) -> dict`

Scan a file for undefined calls using AST analysis.

```python
scan_file("/path/to/project/bad.py")
# => {"success": True, "issues": [{"type": "undefined_call", "name": "...", "line": 7}]}
```

### `validate_types(code: str) -> dict`

Lightweight structural checks on a code snippet:

- iterating over `None`
- wrong argument counts for common builtins (`len`, `sum`, etc.)
- calling constant values
- string methods on non-string constants

```python
validate_types("for x in None:\n    pass")
# => {"success": True, "issues": [{"type": "none_iteration", ...}]}
```

### `find_dead_code(entrypoints: list[str] | None, ignore_patterns: list[str] | None, include_tests: bool = True) -> dict`

Find symbols that appear unused. Provide entrypoints to keep known roots alive.

```python
find_dead_code(entrypoints=["pkg.cli.main"])
# => {"success": True, "dead_symbols": [...], "count": 3}
```

### `explore_call_graph(symbol_name: str) -> dict`

Return definitions, callers, and callees of a symbol.

```python
explore_call_graph("pkg.core.helper")
# => {"success": True, "callers": [...], "callees": [...]}
```

### `search_code(pattern: str, glob: str = "*.py") -> dict`

Regex search across project source files.

```python
search_code(r"def \w+_helper")
```

---

## Typical workflow

1. **`index_project`** on your repo root → builds the symbol table (cached).
2. **`load_project_deps`** → loads dependency APIs.
3. Ask your coding agent to generate code; before accepting, it can:
   - `check_symbol("pkg.core.my_helper")` → ensure it really exists,
   - `check_api("pandas.read_csv")` → confirm the API name,
   - `execute_code(...)` → actually run the snippet and surface errors,
   - `find_dead_code()` → detect newly orphaned code.

---

## Architecture

```
repograph-honest-mcp/
├── repograph_honest/
│   ├── mcp/            # FastMCP server + tool implementations
│   │   ├── server.py   # entry point (mcp.run)
│   │   ├── tools.py    # tool logic
│   │   └── knowledge_base.py  # installed package API cache
│   ├── honest/         # honest action routing
│   │   ├── router.py   # HonestRouter + ToolIntent routing
│   │   └── symbol_index.py    # project-wide symbol index + cache
│   ├── structure/      # tree-sitter based extraction
│   │   ├── extractor.py
│   │   └── relations.py
│   └── sandbox/        # sandboxed execution
├── scripts/
│   └── run_mcp_server.py
├── tests/
├── .github/workflows/  # CI
│   └── ci.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```

Key design decisions:

- **AST-first**: call graphs and file scans use `ast` instead of fragile regex.
- **Module-qualified symbols**: the index stores `pkg.module.func` so cross-file
  references are unambiguous.
- **Lazy loading + caching**: dependency APIs and project indices are cached and
  invalidated by content hash.
- **Thread-safe global state**: tool state is protected by a lock so concurrent
  MCP requests do not race.

---

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check repograph_honest tests scripts
ruff format repograph_honest tests scripts
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for pull-request guidelines.

---

## Sandbox security

`execute_code` runs in a subprocess with timeout protection, a temporary working
directory, and optional Unix resource limits. It is safe against accidental infinite
loops and simple mistakes, but it is **not** a hardened security boundary against
malicious code. For untrusted code, run inside a container or dedicated virtual
machine.

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

---

## License

[MIT](LICENSE)
