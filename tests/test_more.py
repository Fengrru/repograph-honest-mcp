"""Additional coverage tests for router, index caching, extractor, and sandbox."""

from __future__ import annotations

from typing import TYPE_CHECKING

from repograph_honest.honest.router import HonestRouter
from repograph_honest.honest.symbol_index import ProjectIndex, get_project_index
from repograph_honest.mcp.knowledge_base import APIKnowledgeBase
from repograph_honest.structure.extractor import StructureExtractor

if TYPE_CHECKING:
    from pathlib import Path


# ── Router ─────────────────────────────────────────────────────────────
def test_router_route_check_api_finds_reference():
    router = HonestRouter(
        project_symbols={},
        dep_symbols={"pandas.read_csv"},
        dep_kb=APIKnowledgeBase(),
        project_root=".",
    )
    res = router.route("is pandas.read_csv valid?")
    assert res["intent"] == "check_api"
    assert res["api"] == "pandas.read_csv"


def test_router_route_check_api_no_reference():
    router = HonestRouter(project_symbols={}, dep_symbols=set())
    res = router.route("is the api valid")
    assert res["intent"] == "check_api"
    assert "no API reference" in res["result"]


def test_router_route_check_symbol_finds_symbol():
    router = HonestRouter(project_symbols={"myhelper": {}}, dep_symbols=set())
    res = router.route("is myhelper defined")
    assert res["intent"] == "check_symbol"
    assert res["symbol"] == "myhelper"
    assert res["defined"] is True


def test_router_route_scan_file_with_path(tmp_path: Path):
    router = HonestRouter(project_symbols={}, dep_symbols=set())
    res = router.route("scan file please", file_path=str(tmp_path / "a.py"))
    assert res["intent"] == "scan_file"
    assert res["file"] == str(tmp_path / "a.py")


def test_router_route_unknown():
    router = HonestRouter(project_symbols={}, dep_symbols=set())
    res = router.route("hello world random text")
    assert res["intent"] == "unknown"


def test_router_check_call_api():
    router = HonestRouter(project_symbols={}, dep_symbols={"os.path.join"})
    res = router.check_call("os.path.join")
    assert res["valid"] is True


def test_router_check_call_project_symbol():
    router = HonestRouter(project_symbols={"helper": {}}, dep_symbols=set())
    res = router.check_call("helper")
    assert res["valid"] is True
    assert res["source"] == "project"


def test_router_check_call_unknown_high_risk():
    router = HonestRouter(project_symbols={}, dep_symbols=set())
    res = router.check_call("totally_fake_func")
    assert res["valid"] is False
    assert res["risk"] == "high"


def test_router_module_of_without_root(tmp_path: Path):
    router = HonestRouter(project_symbols={}, dep_symbols=set())
    module = router._module_of(str(tmp_path / "src" / "pkg" / "mod.py"))
    assert module.endswith("pkg.mod")


def test_router_check_call_same_module(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir(parents=True)
    router = HonestRouter(project_symbols={}, dep_symbols=set(), project_root=str(tmp_path))
    res = router.check_call("helper", file_path=str(pkg / "helper.py"))
    assert res["valid"] is True
    assert res["source"] == "same_module"


# ── Symbol index caching ───────────────────────────────────────────────
def test_project_index_sqlite_roundtrip(tmp_path: Path):
    idx = ProjectIndex(root=str(tmp_path), symbols={}, files=["a.py"], cache_key="k")
    db = tmp_path / "idx.db"
    idx.to_sqlite(db)
    loaded = ProjectIndex.from_sqlite(db)
    assert loaded is not None
    assert loaded.root == str(tmp_path)


def test_project_index_from_sqlite_missing(tmp_path: Path):
    assert ProjectIndex.from_sqlite(tmp_path / "nope.db") is None


def test_get_project_index_reuses_cache(tmp_path: Path):
    f = tmp_path / "mod.py"
    f.write_text("def foo():\n    pass\n", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    idx1 = get_project_index(tmp_path, force_rebuild=True, cache_dir=cache_dir)
    assert "mod.foo" in idx1.symbols

    # Second call loads from in-memory cache.
    idx2 = get_project_index(tmp_path, cache_dir=cache_dir)
    assert "mod.foo" in idx2.symbols
    assert idx2.cache_key == idx1.cache_key


def test_get_project_index_reads_disk_cache(tmp_path: Path):
    f = tmp_path / "mod.py"
    f.write_text("def foo():\n    pass\n", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    get_project_index(tmp_path, force_rebuild=True, cache_dir=cache_dir)

    # Clear in-memory cache to force disk read.
    from repograph_honest.honest import symbol_index

    symbol_index._index_cache.clear()
    idx = get_project_index(tmp_path, cache_dir=cache_dir)
    assert "mod.foo" in idx.symbols


# ── Knowledge base ─────────────────────────────────────────────────────
def test_knowledge_base_load_failure():
    kb = APIKnowledgeBase()
    assert kb.load_package("nonexistent_pkg_xyz_123") == 0


def test_knowledge_base_search_and_get():
    kb = APIKnowledgeBase()
    kb.load_package("math")
    assert kb.has("math.sqrt")
    assert kb.get("math.sqrt") is not None
    results = kb.search("math.s", limit=3)
    assert len(results) <= 3
    assert len(kb.all_names()) > 0


def test_knowledge_base_load_twice_cached():
    kb = APIKnowledgeBase()
    n1 = kb.load_package("math")
    n2 = kb.load_package("math")
    assert n1 > 0
    assert n2 == n1


# ── Extractor ──────────────────────────────────────────────────────────
def test_extractor_syntax_error_fallback():
    res = StructureExtractor().parse_source("def broken(:")
    assert res.func_defs == {}
    assert res.edges == []


def test_extractor_import_from():
    res = StructureExtractor().parse_source("from typing import List\n")
    assert "typing" in res.imports
    assert res.imported_symbols["List"] == "typing.List"


def test_extractor_relative_import():
    res = StructureExtractor().parse_source("from . import sibling\n")
    assert "." in res.imports


def test_extractor_annotated_assign():
    res = StructureExtractor().parse_source("x: int = 5\n")
    assert "x" in res.var_defs


def test_extractor_local_edge(tmp_path: Path):
    f = tmp_path / "m.py"
    f.write_text(
        "def helper():\n    return 1\n\ndef use():\n    return helper()\n",
        encoding="utf-8",
    )
    res = StructureExtractor().parse_file(f)
    assert any(e.name == "helper" for e in res.edges)


# ── Sandbox ────────────────────────────────────────────────────────────
def test_sandbox_validate_snippet():
    from repograph_honest.sandbox import SandboxExecutor

    res = SandboxExecutor().validate_snippet("print(undefined_symbol)", set())
    assert res.success is False
    assert res.error_type == "NameError"
