"""Project-level binding (``.repograph/``) and MCP client auto-configuration.

``init`` creates a ``.repograph/config.json`` marker next to the project root so
CLI commands can discover the project without being told the path every time —
the same idea as CodeGraph's ``.codegraph/`` binding directory. ``install``
probes well-known MCP client config files and registers the server for you.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

BINDING_DIR = ".repograph"
CONFIG_NAME = "config.json"

# MCP client config locations, probed in this order.
_CLIENT_TARGETS = [
    ("cursor", lambda root: root / ".cursor" / "mcp.json", ".cursor/mcp.json"),
    ("vscode", lambda root: root / ".vscode" / "mcp.json", ".vscode/mcp.json"),
    (
        "claude",
        lambda root: Path.home() / ".claude.json",
        "~/.claude.json",
    ),
]


@dataclass
class Binding:
    root: Path
    config_path: Path


def _server_command() -> list[str]:
    """Command to launch the MCP server from this installation."""
    if shutil.which("repograph-honest-mcp"):
        return ["repograph-honest-mcp"]
    return [sys.executable, "-m", "repograph_honest.mcp.server"]


def init_project(path: str | None = None, force: bool = False) -> dict:
    """Create a ``.repograph/`` binding for *path* (default: cwd)."""
    root = Path(path or os.getcwd()).resolve()
    if not root.is_dir():
        return {"success": False, "error": f"Not a directory: {root}"}
    binding_dir = root / BINDING_DIR
    config_path = binding_dir / CONFIG_NAME
    if config_path.exists() and not force:
        return {
            "success": True,
            "bound": True,
            "root": str(root),
            "config": str(config_path),
            "message": "Already bound (use --force to re-bind)",
        }
    binding_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "root": str(root),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "version": 1,
    }
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return {
        "success": True,
        "bound": True,
        "root": str(root),
        "config": str(config_path),
    }


def uninit_project(path: str | None = None) -> dict:
    """Remove the ``.repograph/`` binding for *path* (default: cwd)."""
    root = Path(path or os.getcwd()).resolve()
    binding_dir = root / BINDING_DIR
    config_path = binding_dir / CONFIG_NAME
    if not config_path.exists():
        return {"success": False, "error": f"No binding found at {root / BINDING_DIR}"}
    shutil.rmtree(binding_dir)
    return {"success": True, "root": str(root), "unbound": True}


def find_project_root(start: str | None = None) -> Path | None:
    """Walk upward from *start* (default: cwd) looking for a project marker.

    Prefers a ``.repograph/`` binding, then falls back to a ``.git`` directory.
    """
    cur = Path(start or os.getcwd()).resolve()
    if not cur.is_dir():
        cur = cur.parent
    for candidate in [cur, *cur.parents]:
        if (candidate / BINDING_DIR / CONFIG_NAME).exists():
            return candidate
        if (candidate / ".git").exists():
            return candidate
    return None


def install_mcp_config(
    path: str | None = None,
    client: str | None = None,
    dry_run: bool = False,
    command: list[str] | None = None,
) -> dict:
    """Register the MCP server with a client's config file.

    Probes Cursor, VS Code and Claude Code config locations and writes the
    stdio server entry. Use ``dry_run=True`` to preview without writing.
    """
    root = Path(path or os.getcwd()).resolve()
    launch = command or _server_command()

    targets = _CLIENT_TARGETS if not client else [t for t in _CLIENT_TARGETS if t[0] == client]
    if not targets:
        return {"success": False, "error": f"Unknown client: {client}"}

    entry = {
        "command": launch[0],
        "args": launch[1:],
    }
    written: list[dict] = []
    skipped: list[dict] = []

    for name, locator, label in targets:
        target = Path(locator(root))
        payload: dict = {}
        if target.exists():
            try:
                payload = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
        # Claude Code stores servers under "mcpServers"; the rest under "servers".
        key = "mcpServers" if name == "claude" else "servers"
        servers = payload.setdefault(key, {})
        servers["repograph-honest"] = entry
        if dry_run:
            skipped.append({"client": name, "path": label, "would_write": True})
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            return {"success": False, "error": f"Cannot write {label}: {exc}"}
        written.append({"client": name, "path": label})

    result: dict = {"success": True, "dry_run": dry_run, "command": launch}
    if written:
        result["written"] = written
    if skipped:
        result["skipped"] = skipped
    return result
