"""``python -m changex_mcp`` → start the stdio FastMCP server.

This mirrors the ``changex-mcp`` console script (and ``uvx changex-mcp``); both
land on :func:`changex_mcp.server.main`, which runs the server over stdio.
"""

from __future__ import annotations

from changex_mcp.server import main

if __name__ == "__main__":
    main()
