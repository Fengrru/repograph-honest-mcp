"""Benchmark HonestCode operations on real projects.

Run from the repository root:

    python scripts/benchmark.py                                  # this repo
    python scripts/benchmark.py --target /path/to/your/project
    python scripts/benchmark.py --repo https://github.com/psf/requests
    python scripts/benchmark.py --repos psf/requests pallets/flask --format markdown

``--repo``/``--repos`` clone external repositories into a temp dir so the
README's performance table is backed by reproducible numbers on real-world
codebases, not just the project itself. ``--format markdown`` emits a table
ready to paste into the README.

The graph tools are measured twice: once cold (SQLite cache miss, full AST
rebuild) and once hot (cache hit) — the hot number is what repeated MCP calls
see, and is the number the README's "<50 ms" claim refers to.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from honestcode.honest.symbol_index import get_project_index  # noqa: E402
from honestcode.mcp.tools import (  # noqa: E402
    check_api,
    explore_call_graph,
    find_dead_code,
    find_similar_code,
    index_project,
    load_package_apis,
    scan_file,
    search_code,
)
from honestcode.structure.extractor import StructureExtractor  # noqa: E402


def _time(fn, repeat=5):
    """Run *fn* *repeat* times and return (median_ms, samples_ms)."""
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples), samples


def _clone(url: str, dest: Path) -> bool:
    proc = subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", url, str(dest)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git clone failed for {url}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return True


def _symbol_count(target: Path) -> int:
    try:
        idx = get_project_index(target, force_rebuild=False)
        return len(idx.symbols)
    except Exception:  # noqa: BLE001
        return 0


def run_benchmark(target: Path, repeat: int) -> dict:
    """Benchmark a single target and return a dict of measured medians (ms)."""
    results: dict = {"target": str(target)}
    py_files = sorted(target.rglob("*.py"), key=lambda p: p.stat().st_size, reverse=True)
    results["py_files"] = len(py_files)
    results["loc"] = sum(
        sum(1 for _ in p.read_text(encoding="utf-8", errors="ignore").splitlines())
        for p in py_files
    )
    results["symbols"] = _symbol_count(target)

    with tempfile.TemporaryDirectory() as td:
        cache_dir = Path(td) / "cache"

        def do_index():
            get_project_index(target, force_rebuild=True, cache_dir=cache_dir)

        results["index_cold_ms"] = _time(do_index, repeat=repeat)[0]

    def do_index_cached():
        get_project_index(target, force_rebuild=False)

    results["index_cached_ms"] = _time(do_index_cached, repeat=repeat)[0]

    index_project(str(target), force_rebuild=True)

    # scan_file — largest file (warmed for steady-state).
    if py_files:
        scan_target = py_files[0]
        StructureExtractor().parse_file(scan_target)
        results["scan_ms"] = _time(lambda: scan_file(str(scan_target)), repeat=repeat)[0]

    load_package_apis("math")
    results["check_api_ms"] = _time(lambda: check_api("math.sqrt"), repeat=repeat)[0]

    symbols = list(get_project_index(target).symbols.keys())
    sym = next((s for s in symbols if not s.startswith("_")), symbols[0] if symbols else None)
    if sym:
        # Cold: force a graph cache miss, then measure a hot cache hit.
        from honestcode.mcp.tools import _get_call_graph, _invalidate_graph_cache

        _invalidate_graph_cache()
        results["graph_cold_ms"] = _time(lambda: _get_call_graph(target), repeat=1)[0]
        results["explore_cg_ms"] = _time(lambda: explore_call_graph(sym), repeat=repeat)[0]

    results["dead_code_ms"] = _time(
        lambda: find_dead_code(include_tests=True), repeat=min(repeat, 3)
    )[0]
    results["similar_ms"] = _time(lambda: find_similar_code(threshold=0.85), repeat=min(repeat, 3))[
        0
    ]
    results["search_ms"] = _time(lambda: search_code(r"def \w+"), repeat=repeat)[0]
    return results


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def render_text(results: list[dict]) -> str:
    lines = ["# HonestCode benchmark"]
    for r in results:
        lines.append(f"\n## {r['target']}")
        lines.append(f"- files: {r['py_files']}, loc: {r['loc']}, symbols: {r['symbols']}")
        lines.append(f"- index (cold): {_fmt(r.get('index_cold_ms'))} ms")
        lines.append(f"- index (cached): {_fmt(r.get('index_cached_ms'))} ms")
        lines.append(f"- scan_file: {_fmt(r.get('scan_ms'))} ms")
        lines.append(f"- check_api: {_fmt(r.get('check_api_ms'))} ms")
        lines.append(f"- graph (cold rebuild): {_fmt(r.get('graph_cold_ms'))} ms")
        lines.append(f"- explore_call_graph (hot): {_fmt(r.get('explore_cg_ms'))} ms")
        lines.append(f"- find_dead_code: {_fmt(r.get('dead_code_ms'))} ms")
        lines.append(f"- find_similar_code: {_fmt(r.get('similar_ms'))} ms")
        lines.append(f"- search_code: {_fmt(r.get('search_ms'))} ms")
    return "\n".join(lines)


def render_markdown(results: list[dict]) -> str:
    headers = [
        "repo",
        "files",
        "loc",
        "symbols",
        "index cold (ms)",
        "index cached (ms)",
        "scan (ms)",
        "graph cold (ms)",
        "call-graph hot (ms)",
        "dead code (ms)",
        "similar (ms)",
        "search (ms)",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "---|" * len(headers),
    ]
    for r in results:
        name = Path(r["target"]).name
        row = [
            name,
            str(r["py_files"]),
            str(r["loc"]),
            str(r["symbols"]),
            _fmt(r.get("index_cold_ms")),
            _fmt(r.get("index_cached_ms")),
            _fmt(r.get("scan_ms")),
            _fmt(r.get("graph_cold_ms")),
            _fmt(r.get("explore_cg_ms")),
            _fmt(r.get("dead_code_ms")),
            _fmt(r.get("similar_ms")),
            _fmt(r.get("search_ms")),
        ]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark HonestCode.")
    parser.add_argument(
        "--target",
        default=str(ROOT),
        help="Project to benchmark against (default: this repo).",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Clone this git repo (URL or owner/name) and benchmark it.",
    )
    parser.add_argument(
        "--repos",
        nargs="*",
        default=None,
        help="Clone these git repos and benchmark each (URLs or owner/name).",
    )
    parser.add_argument("--repeat", type=int, default=5, help="Runs per operation.")
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format (default: text).",
    )
    args = parser.parse_args()

    repos = list(args.repos or [])
    if args.repo:
        repos.insert(0, args.repo)

    results: list[dict] = []
    if repos:
        with tempfile.TemporaryDirectory(prefix="honestcode-bench-") as td:
            for ref in repos:
                url = ref if ref.startswith(("http", "git@")) else f"https://github.com/{ref}"
                name = ref.rstrip("/").split("/")[-1].removesuffix(".git")
                dest = Path(td) / name
                print(f"# Cloning {url} ...", file=sys.stderr)
                _clone(url, dest)
                results.append(run_benchmark(dest, args.repeat))
    else:
        results.append(run_benchmark(Path(args.target), args.repeat))

    print(f"# Python {sys.version.split()[0]}, repeat={args.repeat}\n")
    if args.format == "json":
        print(json.dumps(results, indent=2))
    elif args.format == "markdown":
        print(render_markdown(results))
    else:
        print(render_text(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
