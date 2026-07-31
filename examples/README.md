# Examples

This directory contains short, runnable examples for using RepoGraph-Honest as
a Python library.

You can run any example from the repository root:

```bash
python examples/01_index_and_check.py /path/to/your/project
```

## Available examples

| File | What it demonstrates |
|------|----------------------|
| `01_index_and_check.py` | Index a project and verify a symbol exists |
| `02_check_api.py` | Verify a library API call and catch typos |
| `03_scan_and_validate.py` | Scan a file for undefined calls and type issues |
| `04_dead_code.py` | Find unused symbols with entrypoints |

All examples assume you have installed the package in editable mode:

```bash
pip install -e .
```
