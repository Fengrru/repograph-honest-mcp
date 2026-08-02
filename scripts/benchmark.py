"""Benchmark RepoGraph-Honest operations on a real project.

Run from the repository root:

    python scripts/benchmark.py
    python scripts/benchmark.py --target /path/to/your/project

Prints one line per operation with the measured latency so the README's
performance table can be backed by reproducible numbers rather than
estimates.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from repograph_honest.honest.symbol_index import get_project_index  # noqa: E402
from repograph_honest.mcp.tools import (  # noqa: E402
    _build_call_graph,
    check_api,
    explore_call_graph,
    find_dead_code,
    find_similar_code,
    index_project,
    load_package_apis,
    scan_file,
    search_code,
)
from repograph_honest.structure.extractor import StructureExtractor  # noqa: E402


def _time(fn, repeat=5):
    """Run *fn* *repeat* times and return (median_ms, samples_ms)."""
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples), samples


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark RepoGraph-Honest.")
    parser.add_argument(
        "--target",
        default=str(ROOT),
        help="Project to benchmark against (default: this repo).",
    )
    parser.add_argument("--repeat", type=int, default=5, help="Runs per operation.")
    args = parser.parse_args()

    target = Path(args.target)
    print(f"# RepoGraph-Honest benchmark — target: {target}")
    print(f"# Python {sys.version.split()[0]}, repeat={args.repeat}")
    print()

    # index_project (cold)
    with tempfile.TemporaryDirectory() as td:
        cache_dir = Path(td) / "cache"

        def do_index():
            get_project_index(target, force_rebuild=True, cache_dir=cache_dir)

        med, _ = _time(do_index, repeat=args.repeat)
        print(f"index_project (cold):       {med:>8.1f} ms")

    # index_project (cached)
    def do_index_cached():
        get_project_index(target, force_rebuild=False)

    med, _ = _time(do_index_cached, repeat=args.repeat)
    print(f"index_project (cached):     {med:>8.1f} ms")

    index_project(str(target), force_rebuild=True)

    # scan_file — pick the largest .py file in the project
    py_files = sorted(target.rglob("*.py"), key=lambda p: p.stat().st_size, reverse=True)
    if not py_files:
        print("scan_file: no .py files found")
    else:
        scan_target = py_files[0]
        extractor = StructureExtractor()

        # Warm the extractor so we measure steady-state.
        extractor.parse_file(scan_target)

        def do_scan():
            scan_file(str(scan_target))

        med, _ = _time(do_scan, repeat=args.repeat)
        print(f"scan_file ({scan_target.name}, {scan_target.stat().st_size} B): {med:>6.1f} ms")

    # check_api
    load_package_apis("math")

    def do_check_api():
        check_api("math.sqrt")

    med, _ = _time(do_check_api, repeat=args.repeat)
    print(f"check_api:                  {med:>8.1f} ms")

    # explore_call_graph
    # Find a symbol that has callers/callees.
    from repograph_honest.mcp.tools import _project_index  # noqa: PLC0415

    symbols = list((_project_index.symbols if _project_index else {}).keys())
    sym = next((s for s in symbols if not s.startswith("_")), symbols[0] if symbols else None)

    if sym:
        med, _ = _time(lambda: explore_call_graph(sym), repeat=args.repeat)
        print(f"explore_call_graph ({sym}): {med:>6.1f} ms")

    # find_dead_code
    med, _ = _time(lambda: find_dead_code(include_tests=True), repeat=min(args.repeat, 3))
    print(f"find_dead_code:             {med:>8.1f} ms")

    # find_similar_code
    med, _ = _time(lambda: find_similar_code(threshold=0.85), repeat=min(args.repeat, 3))
    print(f"find_similar_code:          {med:>8.1f} ms")

    # search_code
    med, _ = _time(lambda: search_code(r"def \w+"), repeat=args.repeat)
    print(f"search_code:                {med:>8.1f} ms")

    # _build_call_graph (internal, but documents the cost of graph tools)
    med, _ = _time(lambda: _build_call_graph(target), repeat=min(args.repeat, 3))
    print(f"_build_call_graph:          {med:>8.1f} ms")

    return 0


if __name__ == "__main__":
    sys.exit(main())
