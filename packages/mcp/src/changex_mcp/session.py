"""In-process session state for the stdio MCP server.

The server is single-process and (per the decision) single-session-per-handle:
each ``open_tracked`` mints a ``handle`` mapping to a :class:`Session` bundling
the docx adapter, the on-disk ``.changex`` journal, and the once-captured
``AgentContext``.

Concurrency: the journal persists on every append, and a per-session lock
serializes ``apply``+``append`` so concurrent tool calls within one turn get a
deterministic, server-assigned ``seq`` (the core ``Journal`` owns seq assignment)
and can never interleave a half-applied op with a journal write.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from changex_core.adapters.docx_adapter import DocxAdapter
from changex_core.journal.events import Header
from changex_core.journal.journal import Journal
from changex_core.paths import safe_path

from changex_mcp.provenance import AgentContext


class SessionError(RuntimeError):
    """Raised for unknown handles or duplicate opens of the same document."""


@dataclass
class Session:
    """One open document: adapter + journal + declared agent identity + lock."""

    handle: str
    source_path: Path
    changex_path: Path
    adapter: DocxAdapter
    journal: Journal
    agent_context: AgentContext
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def session_id(self) -> str:
        """The journal's session id (stable identity for provenance)."""
        return self.journal.header.session_id


class SessionStore:
    """Thread-safe registry of open :class:`Session` objects keyed by handle."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._open_paths: dict[str, str] = {}  # resolved source path -> handle
        self._guard = threading.Lock()

    def open(
        self,
        *,
        source_path: str,
        changex_path: Optional[str],
        agent_context: AgentContext,
        author: str,
    ) -> Session:
        """Open a docx, create its journal, and register a new session.

        Refuses to open the same source path twice concurrently (the decision
        declares two-agent access to one doc unsupported, so we guard it rather
        than leave behavior undefined).
        """
        resolved_src = safe_path(source_path, must_exist=True, allow_suffixes=(".docx",))
        with self._guard:
            if str(resolved_src) in self._open_paths:
                raise SessionError(
                    f"document {resolved_src.name!r} is already open in this server; "
                    "close it (save_tracked) before re-opening — concurrent access "
                    "to one document is unsupported."
                )
            handle = uuid.uuid4().hex
            adapter = DocxAdapter.load(str(resolved_src), author=author)
            changex = self._derive_changex_path(changex_path, resolved_src, handle)
            header = Header.create(
                baseline_sha256=adapter.baseline_sha256(),
                filename=resolved_src.name,
                baseline_uri=resolved_src.as_uri(),
                node_id_map=adapter.node_id_map(),
            )
            journal = Journal.open(str(changex), header=header)
            session = Session(
                handle=handle,
                source_path=resolved_src,
                changex_path=changex,
                adapter=adapter,
                journal=journal,
                agent_context=agent_context,
            )
            self._sessions[handle] = session
            self._open_paths[str(resolved_src)] = handle
            return session

    def get(self, handle: str) -> Session:
        """Return the session for ``handle`` or raise :class:`SessionError`."""
        session = self._sessions.get(handle)
        if session is None:
            raise SessionError(f"unknown handle {handle!r}; call open_tracked first")
        return session

    def close(self, handle: str) -> None:
        """Drop a session from the registry, freeing its source path for re-open."""
        with self._guard:
            session = self._sessions.pop(handle, None)
            if session is not None:
                self._open_paths.pop(str(session.source_path), None)

    @staticmethod
    def _derive_changex_path(
        changex_path: Optional[str],
        resolved_src: Path,
        handle: str,
    ) -> Path:
        """Resolve the sidecar journal path, defaulting next to the source doc."""
        if changex_path:
            return safe_path(changex_path, allow_suffixes=(".changex", ".jsonl"))
        default = resolved_src.with_suffix(".changex")
        return safe_path(str(default), allow_suffixes=(".changex", ".jsonl"))
