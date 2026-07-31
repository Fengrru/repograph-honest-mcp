"""Tests for the honest core, extractor, router and sandbox."""

from __future__ import annotations

from pathlib import Path

from repograph_honest.honest.router import HonestRouter, ToolIntent
from repograph_honest.honest.symbol_index import ProjectIndex, get_project_index
from repograph_honest.sandbox import SandboxExecutor
from repograph_honest.structure.extractor import StructureExtractor


# ── Sandbox ────────────────────────────────────────────────────────────
def test_sandbox_runs_valid_code():
    res = SandboxExecutor().execute("print(1 + 1)")
    assert res.success is True
    assert res.stdout.strip() == "2"


def test_sandbox_catches_name_error():
    res = SandboxExecutor().execute("print(undefined_var)")
    assert res.success is False
    assert res.error_type == "NameError"


def test_sandbox_timeout():
    res = SandboxExecutor(timeout=1).execute("import time; time.sleep(10)")
    assert res.success is False
    assert "timed out" in res.error.lower()


# ── StructureExtractor ─────────────────────────────────────────────────
def test_extractor_finds_function_def():
    code = "def foo():\n    return 1\n"
    res = StructureExtractor().parse_source(code)
    assert "foo" in res.func_defs
    assert "foo" not in res.class_defs


def test_extractor_finds_class_def():
    code = "class Bar:\n    def method(self): pass\n"
    res = StructureExtractor().parse_source(code)
    assert "Bar" in res.class_defs
    assert "Bar.method" in res.func_defs
    assert res.func_defs["Bar.method"][0] == 1  # 0-based line index


def test_extractor_imports():
    code = "import os\nfrom typing import List\n"
    res = StructureExtractor().parse_source(code)
    assert "os" in res.imports
    assert "typing" in res.imports


def test_extractor_scan_file(tmp_path: Path):
    f = tmp_path / "sample.py"
    f.write_text("undefined_fn()\nprint(len([1,2,3]))\n", encoding="utf-8")
    issues = StructureExtractor().scan_file(f)
    assert any(i["name"] == "undefined_fn" for i in issues)
    assert not any(i["name"] == "len" for i in issues)


# ── Router ─────────────────────────────────────────────────────────────
def test_router_declares_unknown():
    router = HonestRouter(project_symbols={}, dep_symbols=set())
    dec = router.route("nonexistent_thing")
    assert dec["intent"] == "unknown"


def test_router_resolves_project_symbol():
    router = HonestRouter(
        project_symbols={"my_helper": {"file": "a.py", "line": 1}},
        dep_symbols=set(),
    )
    choice = router.choose_tool("is my_helper defined")
    assert choice.intent == ToolIntent.CHECK_SYMBOL
    dec = router.route("is my_helper defined")
    assert dec["symbol"] == "my_helper"
    assert dec["defined"] is True


def test_router_check_api():
    router = HonestRouter(
        project_symbols={},
        dep_symbols={"os.path.join"},
        project_root=".",
    )
    result = router.check_call("os.path.join")
    assert result["valid"] is True


def test_module_of_relative_to_root():
    router = HonestRouter(project_symbols={}, dep_symbols=set(), project_root="/home/user/proj")
    assert router._module_of("/home/user/proj/src/pkg/mod.py") == "pkg.mod"
    assert router._module_of("/home/user/proj/pkg/__init__.py") == "pkg"


# ── ProjectIndex ───────────────────────────────────────────────────────
def test_get_project_index(tmp_path: Path):
    (tmp_path / "mod.py").write_text("def foo(): pass\n", encoding="utf-8")
    idx = get_project_index(tmp_path, force_rebuild=True, cache_dir=tmp_path / "cache")
    assert "mod.foo" in idx.symbols
    assert idx.symbols["mod.foo"].kind == "function"

    # Cached second time.
    idx2 = get_project_index(tmp_path, cache_dir=tmp_path / "cache")
    assert "mod.foo" in idx2.symbols


def test_index_distinguishes_exported_local(tmp_path: Path):
    (tmp_path / "mod.py").write_text(
        "def public(): pass\ndef _private(): pass\n", encoding="utf-8"
    )
    idx = get_project_index(tmp_path, force_rebuild=True, cache_dir=tmp_path / "cache")
    assert idx.symbols["mod.public"].exported is True
    assert idx.symbols["mod._private"].exported is False


def test_index_rebuilds_on_change(tmp_path: Path):
    f = tmp_path / "mod.py"
    f.write_text("def foo(): pass\n", encoding="utf-8")
    idx = get_project_index(tmp_path, force_rebuild=True, cache_dir=tmp_path / "cache")
    assert "mod.foo" in idx.symbols

    f.write_text("def bar(): pass\n", encoding="utf-8")
    idx = get_project_index(tmp_path, force_rebuild=True, cache_dir=tmp_path / "cache")
    assert "mod.bar" in idx.symbols
    assert "mod.foo" not in idx.symbols


# ── SQLite round-trip ──────────────────────────────────────────────────
def test_sqlite_round_trip(tmp_path: Path):
    idx = ProjectIndex(
        root=str(tmp_path),
        symbols={},
        files=["a.py"],
        cache_key="abc",
    )
    db = tmp_path / "index.db"
    idx.to_sqlite(db)
    loaded = ProjectIndex.from_sqlite(db)
    assert loaded is not None
    assert loaded.root == str(tmp_path)
    assert loaded.files == ["a.py"]
