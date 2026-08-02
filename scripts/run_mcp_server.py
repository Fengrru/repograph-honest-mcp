"""
Launch the HonestCode MCP server.

Usage:
    python scripts/run_mcp_server.py
    python scripts/run_mcp_server.py --transport stdio   # default

The server communicates over stdio by default, which is what MCP clients
(Cursor, Claude Desktop, VS Code) expect.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the package root is importable when run directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from honestcode.mcp.server import mcp  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="HonestCode MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for sse transport")
    parser.add_argument("--port", type=int, default=8000, help="Port for sse transport")
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
