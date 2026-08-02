"""Tests for the command-line interface."""

from __future__ import annotations

import contextlib
import io
import json
from typing import TYPE_CHECKING

import pytest

from honestcode.cli import main as cli_main

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def sample_project(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "core.py").write_text(
        "def helper():\n    return 1\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "unused.py").write_text("def orphan():\n    return 42\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest>=7.0\n", encoding="utf-8")
    return tmp_path


def _run(argv: list[str]) -> tuple[int, dict]:
    """Run the CLI with *argv* and return (exit_code, parsed_json).

    The CLI writes JSON to stdout; we capture and parse it.
    """
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = cli_main(argv)
    except SystemExit as e:  # argparse may raise on bad input
        return int(e.code or 0), {}
    out = buf.getvalue().strip()
    try:
        return code, json.loads(out)
    except json.JSONDecodeError:
        return code, {"_raw": out}


def test_cli_index(sample_project: Path):
    code, res = _run(["index", str(sample_project)])
    assert code == 0
    assert res["success"] is True
    assert res["symbols_indexed"] >= 2
    assert res["root"] == str(sample_project.resolve())


def test_cli_index_force(sample_project: Path):
    code, res = _run(["index", str(sample_project), "--force"])
    assert code == 0
    assert res["cached"] is False


def test_cli_index_missing_path():
    code, res = _run(["index", "/nonexistent/xyz"])
    assert code == 1
    assert res["success"] is False


def test_cli_deps(sample_project: Path):
    code, res = _run(["deps", str(sample_project)])
    assert code == 0
    assert res["success"] is True
    assert "pytest" in res["packages_loaded"]


def test_cli_scan_clean_file(sample_project: Path):
    bad = sample_project / "clean.py"
    bad.write_text("print(1 + 1)\n", encoding="utf-8")
    _run(["index", str(sample_project), "--force"])
    code, res = _run(["scan", str(bad)])
    assert code == 0  # no issues -> exit 0
    assert res["success"] is True
    assert res["issues"] == []


def test_cli_scan_dirty_file(sample_project: Path):
    bad = sample_project / "bad.py"
    bad.write_text("nonexistent_func()\n", encoding="utf-8")
    _run(["index", str(sample_project), "--force"])
    code, res = _run(["scan", str(bad)])
    assert code == 1  # issues found -> exit 1
    assert res["success"] is True
    assert any(i["name"] == "nonexistent_func" for i in res["issues"])


def test_cli_check_symbol_defined(sample_project: Path):
    _run(["index", str(sample_project), "--force"])
    code, res = _run(["check-symbol", "pkg.core.helper"])
    assert code == 0
    assert res["defined"] is True


def test_cli_check_symbol_undefined(sample_project: Path):
    _run(["index", str(sample_project), "--force"])
    code, res = _run(["check-symbol", "pkg.core.nope"])
    assert code == 1
    assert res["defined"] is False


def test_cli_check_api_known():
    _run(["load-package", "math"])
    code, res = _run(["check-api", "math.sqrt"])
    assert code == 0
    assert res["valid"] is True


def test_cli_check_api_typo():
    _run(["load-package", "math"])
    code, res = _run(["check-api", "math.sqrtt"])
    assert code == 1
    assert res["valid"] is False
    assert res.get("suggestion")


def test_cli_validate_clean():
    code, res = _run(["validate", "x = [1, 2, 3]\nprint(len(x))\n"])
    assert code == 0
    assert res["issues"] == []


def test_cli_validate_dirty():
    code, res = _run(["validate", "for x in None:\n    pass\n"])
    assert code == 1
    assert any(i["type"] == "none_iteration" for i in res["issues"])


def test_cli_dead_code(sample_project: Path):
    _run(["index", str(sample_project), "--force"])
    code, res = _run(
        [
            "dead-code",
            "--entrypoints",
            "pkg.core.main",
            "--no-tests",
        ]
    )
    assert code == 1  # orphan is dead
    dead_names = {d["symbol"] for d in res["dead_symbols"]}
    assert "pkg.unused.orphan" in dead_names


def test_cli_call_graph(sample_project: Path):
    _run(["index", str(sample_project), "--force"])
    code, res = _run(["call-graph", "pkg.core.helper"])
    assert code == 0
    assert res["success"] is True
    assert len(res["definitions"]) >= 1
    callers = {c["caller"] for c in res["callers"]}
    assert "pkg.core.main" in callers


def test_cli_search(sample_project: Path):
    _run(["index", str(sample_project), "--force"])
    code, res = _run(["search", r"def \w+"])
    assert code == 1  # matches found -> exit 1
    assert res["count"] >= 2


def test_cli_search_bad_regex(sample_project: Path):
    _run(["index", str(sample_project), "--force"])
    code, res = _run(["search", r"("])
    assert code == 1
    assert "Invalid regex" in res.get("error", "")


def test_cli_stats(sample_project: Path):
    _run(["index", str(sample_project), "--force"])
    code, res = _run(["stats"])
    assert code == 0
    assert res["success"] is True
    assert res["indexed"] is True


def test_cli_choose_tool():
    code, res = _run(["choose-tool", "is my_symbol defined"])
    assert code == 0
    assert res["tool"] == "check_symbol"


def test_cli_no_command_errors():
    with pytest.raises(SystemExit):
        cli_main([])


def test_cli_unknown_command_errors():
    with pytest.raises(SystemExit):
        cli_main(["frobnicate"])


def test_cli_entry_point_installed():
    """The `honestcode` console script must be declared and importable."""
    # We don't actually shell out (would need install); we verify the module
    # exposes a main() callable that argparse can drive.
    from honestcode.cli import main

    assert callable(main)
