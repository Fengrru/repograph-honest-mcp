"""
Project-wide symbol index.

Builds a unified view of every function, class, and variable defined in a
project, and caches the result to disk.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from honestcode.structure.extractor import StructureExtractor

logger = logging.getLogger(__name__)

__all__ = ["SymbolInfo", "SymbolIndex", "ProjectIndex", "get_project_index"]


@dataclass
class SymbolInfo:
    file: str
    line: int
    kind: str
    exported: bool = True


@dataclass
class SymbolIndex:
    symbols: dict[str, SymbolInfo] = field(default_factory=dict)

    @property
    def exported_symbols(self) -> dict[str, SymbolInfo]:
        return {n: i for n, i in self.symbols.items() if i.exported}

    @property
    def local_symbols(self) -> dict[str, SymbolInfo]:
        return {n: i for n, i in self.symbols.items() if not i.exported}


@dataclass
class ProjectIndex:
    root: str
    symbols: dict[str, SymbolInfo]
    files: list[str]
    cache_key: str = ""

    def to_sqlite(self, db_path: str | Path) -> None:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TABLE IF EXISTS symbols")
        conn.execute(
            "CREATE TABLE symbols (name TEXT PRIMARY KEY, file TEXT, line INTEGER, kind TEXT, exported INTEGER)"  # noqa: E501
        )
        for name, info in self.symbols.items():
            conn.execute(
                "INSERT OR REPLACE INTO symbols VALUES (?, ?, ?, ?, ?)",
                (name, info.file, info.line, info.kind, int(info.exported)),
            )
        conn.execute("DROP TABLE IF EXISTS meta")
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO meta VALUES (?, ?)", ("root", self.root))
        conn.execute("INSERT INTO meta VALUES (?, ?)", ("files", json.dumps(self.files)))
        conn.commit()
        conn.close()

    @classmethod
    def from_sqlite(cls, db_path: str | Path) -> ProjectIndex | None:
        import sqlite3

        p = Path(db_path)
        if not p.exists():
            return None
        try:
            conn = sqlite3.connect(str(p))
            cur = conn.cursor()
            cur.execute("SELECT name, file, line, kind, exported FROM symbols")
            symbols = {
                name: SymbolInfo(file=f, line=line, kind=kind, exported=bool(exported))
                for name, f, line, kind, exported in cur.fetchall()
            }
            cur.execute("SELECT key, value FROM meta")
            meta = dict(cur.fetchall())
            conn.close()
            return cls(
                root=meta.get("root", ""),
                symbols=symbols,
                files=json.loads(meta.get("files", "[]")),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to load SQLite index from %s: %s", db_path, e)
            return None


def _should_rebuild(root: Path, cache_path: Path) -> bool:
    """Determine whether the on-disk cache is stale.

    Considers file list, content hashes, and mtime for robust invalidation.
    """
    if not cache_path.exists():
        return True

    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return True

    current_files = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*.py")
        if not p.name.startswith(".") and "__pycache__" not in p.parts
    )
    if cache.get("files") != current_files:
        return True

    old_hashes = cache.get("hashes", {})
    for rel in current_files:
        p = root / rel
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
        except Exception:  # noqa: BLE001
            return True
        if old_hashes.get(rel) != digest:
            return True

    return False


def _build_cache_key(root: Path) -> str:
    """Build a deterministic cache key from file contents."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.py")):
        if p.name.startswith(".") or "__pycache__" in p.parts:
            continue
        try:
            h.update(p.read_bytes())
        except Exception:  # noqa: BLE001
            continue
    return h.hexdigest()


def _index_directory(root: Path, extractor: StructureExtractor) -> ProjectIndex:
    symbols: dict[str, SymbolInfo] = {}
    files: list[str] = []
    for p in sorted(root.rglob("*.py")):
        if p.name.startswith(".") or "__pycache__" in p.parts:
            continue
        rel = str(p.relative_to(root))
        files.append(rel)
        try:
            res = extractor.parse_file(p)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to parse %s: %s", p, e)
            continue
        _merge(p, root, res, symbols)

    return ProjectIndex(
        root=str(root),
        symbols=symbols,
        files=files,
        cache_key=_build_cache_key(root),
    )


def _module_name(file: Path, root: Path) -> str:
    """Infer a dotted module name from *file* relative to *root*.

    Only strips the ``src`` prefix when it is a standalone directory component
    (i.e. the standard ``src`` layout) and there are further path segments.
    """
    try:
        rel = file.resolve().relative_to(root.resolve())
    except ValueError:
        rel = file
    parts = list(rel.with_suffix("").parts)
    # Only strip "src" if it is a real layout prefix (has sub-packages after it).
    if len(parts) > 1 and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _merge(file: Path, root: Path, res, symbols: dict[str, SymbolInfo]) -> None:
    """Merge a ParseResult's definitions into the global symbol table."""
    rel = "/".join(file.relative_to(root).parts)
    module = _module_name(file, root)

    def _add(name: str, line: int, kind: str) -> None:
        full_name = f"{module}.{name}" if module and name else (name or module)
        exported = not name.split(".")[-1].startswith("_") if name else True
        symbols[full_name] = SymbolInfo(file=rel, line=line, kind=kind, exported=exported)

    for fn, (s, _e) in res.func_defs.items():
        _add(fn, s + 1, "function")
    for cn, (s, _e) in res.class_defs.items():
        _add(cn, s + 1, "class")
    for vn, (s, _e) in res.var_defs.items():
        _add(vn, s + 1, "variable")


# Module-level cache to avoid re-indexing within a single process.
_index_cache: dict[str, ProjectIndex] = {}


def get_project_index(
    root: str | Path,
    force_rebuild: bool = False,
    cache_dir: str | Path | None = None,
) -> ProjectIndex:
    """Return (and cache) the project index for *root*."""
    root = Path(root)
    resolved = root.resolve()
    cache_dir = Path(cache_dir or os.path.expanduser("~/.cache/honestcode"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{resolved.name}_{_stable_hash(str(resolved))}.json"

    if not force_rebuild:
        cached = _index_cache.get(str(resolved))
        if cached is not None:
            return cached

        if not _should_rebuild(resolved, cache_path):
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                symbols = {n: SymbolInfo(**i) for n, i in data.get("symbols", {}).items()}
                idx = ProjectIndex(
                    root=data.get("root", str(resolved)),
                    symbols=symbols,
                    files=data.get("files", []),
                    cache_key=data.get("cache_key", ""),
                )
                _index_cache[str(resolved)] = idx
                return idx
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to load cache %s: %s", cache_path, e)

    extractor = StructureExtractor()
    idx = _index_directory(resolved, extractor)

    try:
        cache_path.write_text(
            json.dumps(
                {
                    "root": idx.root,
                    "symbols": {n: asdict(i) for n, i in idx.symbols.items()},
                    "files": idx.files,
                    "cache_key": idx.cache_key,
                    "hashes": _file_hashes(resolved),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to write cache %s: %s", cache_path, e)

    _index_cache[str(resolved)] = idx
    return idx


def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for p in sorted(root.rglob("*.py")):
        if p.name.startswith(".") or "__pycache__" in p.parts:
            continue
        try:
            hashes[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
        except Exception:  # noqa: BLE001
            continue
    return hashes
