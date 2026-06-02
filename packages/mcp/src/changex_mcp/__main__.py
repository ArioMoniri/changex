"""``python -m changex_mcp`` → start the FastMCP server.

This mirrors the ``changex-mcp`` console script (and ``uvx changex-mcp``); both
land on :func:`changex_mcp.server.main`, which runs stdio by default or the remote
HTTP transport when ``--http`` / ``--sse`` (or ``CHANGEX_MCP_TRANSPORT``) is given.
"""

from __future__ import annotations

from changex_mcp.server import main

if __name__ == "__main__":
    main()
