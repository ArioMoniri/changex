"""ChangeX MCP server: edit a .docx over MCP, get native Word revisions + a journal.

This package wraps the :mod:`changex_core` spine in a stdio FastMCP server. An
agent (any MCP client — Claude Code/Desktop, OpenAI, Gemini CLI) opens a .docx,
makes small intent-named edits, and gets back a Word file with native
accept/reject revisions plus a portable, hash-chained ``.changex`` provenance
journal.

Public surface (used by tests and the entry point):

Server
    ``server.mcp`` — the configured :class:`FastMCP` app; ``server.main`` — the
    ``python -m changex_mcp`` / ``changex-mcp`` entry point.

Tools (transport-independent, unit-testable)
    ``tools.open_tracked``, ``tools.get_outline``, ``tools.edit``,
    ``tools.save_tracked``, ``tools.get_changes``, ``tools.render_review`` —
    plus ``tools.ToolError`` for structured boundary errors.

State / provenance
    ``session.SessionStore`` / ``session.Session`` and
    ``provenance.build_provenance`` / ``provenance.AgentContext``.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
