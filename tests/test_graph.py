"""Tests for the persistent graph layer and CodeGraph-alignment features."""

from __future__ import annotations

import json
import subprocess
import time
from typing import TYPE_CHECKING

import pytest

from honestcode.cli import main as cli_main
from honestcode.graph.graph_store import CallGraph, GraphCache
from honestcode.graph.watcher import ProjectWatcher
from honestcode.honest import project_binding as binding
from honestcode.mcp import tools as _tools

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.usefixtures("tmp_cache_dir")


@pytest.fixture
def tmp_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = tmp_path / "cache"
    monkeypatch.setenv("HONESTCODE_CACHE_DIR", str(cache))
    monkeypatch.setenv("HONESTCODE_INDEX_DIR", str(tmp_path / "index"))
    yield cache


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "core.py").write_text(
        "def helper():\n    return 1\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "test_core.py").write_text(
        "from pkg.core import main\n\ndef test_main():\n    assert main() == 1\n",
        encoding="utf-8",
    )
    return tmp_path


def _run_cli(argv: list[str]) -> tuple[int, dict]:
    """Run the CLI and capture (exit_code, parsed JSON output)."""
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli_main(argv)
    try:
        return code, json.loads(buf.getvalue())
    except json.JSONDecodeError:
        return code, {}


# ── GraphCache persistence -------------------------------------------------


def test_graph_cache_roundtrip(tmp_cache_dir: Path, sample_project: Path):
    graph = CallGraph(
        definitions={"pkg.core.helper": [(sample_project / "pkg" / "core.py", 1, 2, "function")]},
        references={
            "pkg.core.helper": [(sample_project / "pkg" / "core.py", 5, "call", "pkg.core.main")]
        },
    )
    cache = GraphCache.for_root(sample_project, tmp_cache_dir)
    cache.save(graph, sample_project)
    assert cache.is_fresh(sample_project)

    loaded = cache.load()
    assert loaded is not None
    assert "pkg.core.helper" in loaded.definitions
    assert loaded.definitions["pkg.core.helper"][0][1] == 1
    assert loaded.references["pkg.core.helper"][0][3] == "pkg.core.main"


def test_graph_cache_detects_file_change(tmp_cache_dir: Path, sample_project: Path):
    cache = GraphCache.for_root(sample_project, tmp_cache_dir)
    cache.save(CallGraph(), sample_project)
    assert cache.is_fresh(sample_project)

    (sample_project / "pkg" / "core.py").write_text(
        "def helper():\n    return 2\n", encoding="utf-8"
    )
    assert not cache.is_fresh(sample_project)


def test_graph_cache_load_missing(tmp_cache_dir: Path, sample_project: Path):
    cache = GraphCache.for_root(sample_project, tmp_cache_dir)
    assert cache.load() is None


# ── search_code FTS5 acceleration ------------------------------------------


def test_search_code_uses_fts5(tmp_cache_dir: Path, sample_project: Path):
    _tools.index_project(str(sample_project), force_rebuild=True)
    res = _tools.search_code(r"helper")
    assert res["success"]
    assert res["count"] >= 1
    assert res["engine"] == "fts5"

    res2 = _tools.search_code(r"def \w+")
    assert res2["success"]
    assert res2["count"] >= 2


# ── explore_impact ----------------------------------------------------------


def test_explore_impact(tmp_cache_dir: Path, sample_project: Path):
    _tools.index_project(str(sample_project), force_rebuild=True)
    res = _tools.explore_impact("pkg.core.main")
    assert res["success"]
    assert res["counts"]["symbols"] >= 1
    # main is called by the test file, so it should ripple into tests
    assert any("test" in f.lower() for f in res["impacted_files"])


def test_explore_impact_unknown_symbol(tmp_cache_dir: Path, sample_project: Path):
    _tools.index_project(str(sample_project), force_rebuild=True)
    res = _tools.explore_impact("no.such.symbol")
    assert not res["success"]


def test_call_graph_includes_impact_summary(tmp_cache_dir: Path, sample_project: Path):
    _tools.index_project(str(sample_project), force_rebuild=True)
    res = _tools.explore_call_graph("pkg.core.main")
    assert res["success"]
    assert "impact" in res
    assert "symbols" in res["impact"]


# ── affected_files ----------------------------------------------------------


@pytest.fixture
def git_project(tmp_path: Path) -> Path:
    project = tmp_path / "repo"
    pkg = project / "app"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core.py").write_text(
        "def helper():\n    return 1\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    (project / "test_app.py").write_text(
        "from app.core import main\n\ndef test_main():\n    assert main() == 1\n",
        encoding="utf-8",
    )
    # Minimal repo with user identity to satisfy git.
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    for cmd in [
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"],
    ]:
        subprocess.run(cmd, cwd=project, env={**env, **__import__("os").environ}, check=True)
    return project


def test_affected_files_finds_tests(tmp_cache_dir: Path, git_project: Path):
    _tools.index_project(str(git_project), force_rebuild=True)

    # Modify core.py in the working tree; HEAD still has the old version.
    (git_project / "app" / "core.py").write_text(
        "def helper():\n    return 2\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    res = _tools.affected_files(base="HEAD")
    assert res["success"]
    assert any("app/core.py" in f or f.endswith("core.py") for f in res["changed"])
    assert any("test_app.py" in f for f in res["affected_tests"])


def test_affected_files_needs_index(tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(_tools, "_project_root", None)
    monkeypatch.setattr(_tools, "_project_index", None)
    res = _tools.affected_files(base="HEAD")
    assert not res["success"]


# ── ProjectWatcher ----------------------------------------------------------


def test_watcher_fires_after_debounce(tmp_path: Path):
    project = tmp_path / "watched"
    project.mkdir()
    (project / "a.py").write_text("x = 1\n", encoding="utf-8")

    fired: list[list] = []
    watcher = ProjectWatcher(project, fired.append, debounce=0.3, poll_interval=0.05)
    watcher.start()
    try:
        time.sleep(0.2)
        (project / "a.py").write_text("x = 2\n", encoding="utf-8")
        deadline = time.monotonic() + 5
        while not fired and time.monotonic() < deadline:
            time.sleep(0.05)
        assert fired, "watcher never fired after a file change"
        assert any("a.py" in str(p) for p in fired[0])
    finally:
        watcher.stop()


# ── project binding ---------------------------------------------------------


def test_init_uninit_root(tmp_path: Path):
    res = binding.init_project(str(tmp_path))
    assert res["success"] and res["bound"]
    assert (tmp_path / ".honestcode" / "config.json").exists()

    assert binding.find_project_root(str(tmp_path)) == tmp_path.resolve()

    res2 = binding.uninit_project(str(tmp_path))
    assert res2["success"]
    assert not (tmp_path / ".honestcode").exists()
    assert binding.find_project_root(str(tmp_path)) is None


def test_install_dry_run_does_not_write(tmp_path: Path):
    res = binding.install_mcp_config(path=str(tmp_path), client="vscode", dry_run=True)
    assert res["success"] and res["dry_run"]
    assert res["skipped"]
    assert not (tmp_path / ".vscode" / "mcp.json").exists()


def test_install_writes_vscode_config(tmp_path: Path):
    res = binding.install_mcp_config(path=str(tmp_path), client="vscode")
    assert res["success"]
    config = json.loads((tmp_path / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    assert "honestcode" in config["servers"]


# ── CLI: new subcommands ----------------------------------------------------


def test_cli_impact(sample_project: Path):
    _tools.index_project(str(sample_project), force_rebuild=True)
    code, out = _run_cli(["impact", "pkg.core.main"])
    assert code == 0
    assert out["success"]


def test_cli_init_root(tmp_path: Path):
    code, out = _run_cli(["init", str(tmp_path)])
    assert code == 0 and out["bound"]
    code2, root = _run_cli(["root", str(tmp_path)])
    assert code2 == 0
    assert root["root"] == str(tmp_path.resolve())


def test_cli_watch_accepts_flag(sample_project: Path):
    """watch subcommand indexes successfully (it blocks; just check startup)."""
    code, out = _run_cli(["index", str(sample_project), "--watch"])
    assert code == 0
    assert out["success"]
    assert out["watching"] is True
    _tools.stop_watching()


# ── multi-language scan degradation -----------------------------------------


def test_scan_js_without_tree_sitter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from honestcode.structure import multi_lang

    def _boom():
        raise multi_lang.TreeSitterUnavailable("tree-sitter is not installed")

    monkeypatch.setattr(multi_lang, "_import_tree_sitter", _boom)

    js = tmp_path / "app.js"
    js.write_text("function foo() { return bar(); }\n", encoding="utf-8")
    res = _tools.scan_file(str(js))
    # Without the optional extras, tree-sitter is missing → clear message.
    assert not res["success"]
    assert "multi-language" in res["error"]


def test_scan_unknown_extension(tmp_path: Path):
    f = tmp_path / "readme.txt"
    f.write_text("hello\n", encoding="utf-8")
    res = _tools.scan_file(str(f))
    assert not res["success"]


# ── stop_watching -----------------------------------------------------------


def test_stop_watching_noop():
    res = _tools.stop_watching()
    assert res["success"]
    assert res["watching"] is False
