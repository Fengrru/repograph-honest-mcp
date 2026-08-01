"""Tests for the MCP server layer and shared AST utilities."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from repograph_honest.mcp.server import (
    mcp_check_api,
    mcp_check_symbol,
    mcp_choose_tool,
    mcp_execute_code,
    mcp_explore_call_graph,
    mcp_find_dead_code,
    mcp_find_similar_code,
    mcp_get_project_stats,
    mcp_index_project,
    mcp_load_package_apis,
    mcp_load_project_deps,
    mcp_scan_file,
    mcp_search_code,
    mcp_validate_types,
)
from repograph_honest.mcp.tools import check_symbol, validate_types
from repograph_honest.structure.utils import call_base, call_name

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def sample_project(tmp_path: Path):
    """Create a tiny project with a few functions and a class."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "core.py").write_text(
        "def helper():\n    return 1\n\n"
        "def main():\n    return helper()\n\n"
        "class Worker:\n    def work(self):\n        return helper()\n",
        encoding="utf-8",
    )
    return tmp_path


def test_mcp_index_project(sample_project: Path):
    res = mcp_index_project(str(sample_project))
    assert res["success"] is True
    assert res["symbols_indexed"] >= 3
    assert res["root"] == str(sample_project.resolve())


def test_mcp_index_project_missing_path():
    res = mcp_index_project("/nonexistent/path/xyz")
    assert res["success"] is False
    assert "does not exist" in res["error"]


def test_mcp_load_project_deps(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("pytest>=7.0\n", encoding="utf-8")
    res = mcp_load_project_deps(str(tmp_path))
    assert res["success"] is True


def test_mcp_check_symbol(sample_project: Path):
    mcp_index_project(str(sample_project))
    res = mcp_check_symbol("pkg.core.main")
    assert res["defined"] is True
    res = mcp_check_symbol("pkg.core.nope")
    assert res["defined"] is False


def test_mcp_check_api():
    mcp_load_package_apis("math")
    res = mcp_check_api("math.sqrt")
    assert res["valid"] is True
    res = mcp_check_api("math.sqrtt")
    assert res["valid"] is False
    assert res["suggestion"]


def test_mcp_execute_code():
    res = mcp_execute_code("print(1 + 1)")
    assert res["success"] is True
    assert "2" in res["output"]


def test_mcp_scan_file(sample_project: Path):
    bad = sample_project / "bad.py"
    bad.write_text("nonexistent_func()\n", encoding="utf-8")
    mcp_index_project(str(sample_project))
    res = mcp_scan_file(str(bad))
    assert res["success"] is True
    assert any(i["name"] == "nonexistent_func" for i in res["issues"])


def test_mcp_scan_file_missing():
    res = mcp_scan_file("/nonexistent/file.py")
    assert res["success"] is False


def test_mcp_validate_types():
    res = mcp_validate_types("for x in None:\n    pass\n")
    assert res["success"] is True
    assert any(i["type"] == "none_iteration" for i in res["issues"])


def test_mcp_find_dead_code(sample_project: Path):
    mcp_index_project(str(sample_project))
    res = mcp_find_dead_code(entrypoints=["pkg.core.main"], include_tests=False)
    assert res["success"] is True


def test_mcp_find_similar_code(sample_project: Path):
    mcp_index_project(str(sample_project))
    res = mcp_find_similar_code(threshold=0.99)
    assert res["success"] is True
    assert res["count"] == 0  # no duplicate functions in sample project


def test_mcp_explore_call_graph(sample_project: Path):
    mcp_index_project(str(sample_project))
    res = mcp_explore_call_graph("pkg.core.helper")
    assert res["success"] is True
    assert len(res["definitions"]) >= 1
    assert any(c["caller"] == "main" or c["caller"] == "work" for c in res["callers"])


def test_mcp_search_code(sample_project: Path):
    mcp_index_project(str(sample_project))
    res = mcp_search_code(r"def \w+")
    assert res["success"] is True
    assert res["count"] >= 3


def test_mcp_search_code_bad_regex(sample_project: Path):
    mcp_index_project(str(sample_project))
    res = mcp_search_code(r"(")
    assert res["success"] is False
    assert "Invalid regex" in res["error"]


def test_mcp_choose_tool():
    res = mcp_choose_tool("check if my_symbol is defined")
    assert res["tool"] == "check_symbol"


def test_mcp_get_project_stats(sample_project: Path):
    res = mcp_get_project_stats()
    assert res["indexed"] is True


def test_mcp_get_project_stats_not_indexed(monkeypatch):
    monkeypatch.setattr("repograph_honest.mcp.tools._project_index", None)
    res = mcp_get_project_stats()
    assert res["success"] is False


# ── Utils ──────────────────────────────────────────────────────────────
def test_call_name_name():
    node = ast.parse("foo()").body[0].value.func  # type: ignore[attr-defined]
    assert call_name(node) == "foo"


def test_call_name_attribute_chain():
    node = ast.parse("obj.attr.method()").body[0].value.func  # type: ignore[attr-defined]
    assert call_name(node) == "obj.attr.method"


def test_call_name_complex_expr():
    node = ast.parse("(a + b).foo()").body[0].value.func  # type: ignore[attr-defined]
    assert call_name(node) is None


def test_call_name_none():
    assert call_name(ast.Constant(value=1)) is None


def test_call_base():
    assert call_base("pkg.module.func") == "pkg"
    assert call_base("func") == "func"


def test_validate_types_bad_builtin_kwarg():
    res = validate_types("len(x=1)\n")
    assert res["success"] is True
    assert any(i["type"] == "arg_count" for i in res["issues"])


def test_check_symbol_before_index(monkeypatch):
    monkeypatch.setattr("repograph_honest.mcp.tools._project_index", None)
    res = check_symbol("anything")
    assert res["success"] is False
    assert "indexed" in res["error"]
