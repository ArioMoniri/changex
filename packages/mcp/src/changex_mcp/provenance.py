"""Provenance capture, split honestly into *observed* vs *declared*.

The tech-lead decision is that MCP cannot magically observe everything the
marketing copy implied. So this module makes the split explicit:

* **observed** — what the server can populate from call context without trusting
  the agent: ``ts`` (server clock), ``session_id`` (assigned at ``open_tracked``),
  ``tool_call_id`` (the transport request id), and ``client_name`` /
  ``client_version`` (from the MCP ``clientInfo`` handshake).
* **declared** — what only the agent can supply and the server cannot verify, so
  it is optional and may be ``null``: ``agent`` (model id), ``vendor``,
  ``turn_id``, ``prompt`` (hashed to ``prompt_sha256``), and ``rationale``.

``provenance_source`` records which layer dominated a given event, so a journal
never presents a declared value as if the server observed it. Nothing is keyed on
``tool_call_id`` — identity is ``session_id`` + the server-assigned ``seq``.

The module also normalizes argument types, because some MCP clients stringify
numbers/bools. ``coerce_int`` / ``coerce_bool`` accept the common forms and reject
the genuinely ambiguous ones rather than silently guessing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Optional

from changex_core.journal.events import Provenance, utc_now_iso


@dataclass
class AgentContext:
    """The once-per-session declared identity supplied at ``open_tracked``.

    Captured once (not per op) per the decision to avoid per-call attribution
    drift. All fields are optional; absence is honestly represented as ``null``.
    """

    agent: Optional[str] = None  # model id, e.g. "claude-opus-4-8"
    vendor: Optional[str] = None  # e.g. "anthropic", "openai", "google"

    @classmethod
    def from_obj(cls, obj: Any) -> "AgentContext":
        """Build from a loosely-typed ``{model|agent, vendor}`` dict (or ``None``)."""
        if not obj:
            return cls()
        if not isinstance(obj, dict):
            return cls()
        agent = obj.get("agent") or obj.get("model") or obj.get("model_id")
        vendor = obj.get("vendor") or obj.get("provider")
        return cls(
            agent=str(agent) if agent else None,
            vendor=str(vendor) if vendor else None,
        )


@dataclass
class ObservedContext:
    """What the server pulled from the MCP call context for one tool call."""

    tool_call_id: Optional[str] = None
    client_name: Optional[str] = None
    client_version: Optional[str] = None


def observed_from_mcp(ctx: Any) -> ObservedContext:
    """Extract observable provenance from a FastMCP ``Context`` defensively.

    The SDK surface shifts between versions and some clients omit ``clientInfo``
    entirely, so every access is guarded — a missing field yields ``None`` rather
    than raising, because provenance capture must never break an edit.
    """
    tool_call_id: Optional[str] = None
    client_name: Optional[str] = None
    client_version: Optional[str] = None

    if ctx is None:
        return ObservedContext()

    # The transport request id is the closest thing MCP gives us to a per-call id.
    for getter in ("request_id",):
        tool_call_id = _safe_getattr(ctx, getter) or tool_call_id
    request_context = _safe_getattr(ctx, "request_context")
    if request_context is not None and tool_call_id is None:
        tool_call_id = _safe_getattr(request_context, "request_id")

    # clientInfo from the initialize handshake → client name/version.
    client_params = None
    session = _safe_getattr(ctx, "session")
    if session is not None:
        client_params = _safe_getattr(session, "client_params")
    if client_params is None and request_context is not None:
        rc_session = _safe_getattr(request_context, "session")
        if rc_session is not None:
            client_params = _safe_getattr(rc_session, "client_params")
    if client_params is not None:
        client_info = _safe_getattr(client_params, "clientInfo")
        if client_info is not None:
            client_name = _safe_getattr(client_info, "name")
            client_version = _safe_getattr(client_info, "version")

    return ObservedContext(
        tool_call_id=_as_str_or_none(tool_call_id),
        client_name=_as_str_or_none(client_name),
        client_version=_as_str_or_none(client_version),
    )


def build_provenance(
    *,
    session_id: str,
    observed: ObservedContext,
    agent_context: AgentContext,
    rationale: Optional[str] = None,
    prompt: Optional[str] = None,
    prompt_sha256: Optional[str] = None,
    turn_id: Optional[str] = None,
) -> Provenance:
    """Assemble a core :class:`Provenance` from the observed + declared layers.

    ``provenance_source`` is ``'declared'`` when any agent-supplied attribution
    (agent id, vendor, rationale, prompt, turn) is present — signalling that the
    record leans on values the server could not independently verify — and
    ``'observed'`` otherwise.

    ``prompt`` is hashed (never stored verbatim) into ``prompt_sha256``; an
    explicit ``prompt_sha256`` argument wins if both are given.
    """
    digest = prompt_sha256 or (sha256_text(prompt) if prompt else None)
    declared_present = any(
        (agent_context.agent, agent_context.vendor, rationale, digest, turn_id)
    )
    return Provenance(
        ts=utc_now_iso(),
        session_id=session_id,
        tool_call_id=observed.tool_call_id,
        client_name=observed.client_name,
        client_version=observed.client_version,
        agent=agent_context.agent,
        vendor=agent_context.vendor,
        turn_id=_as_str_or_none(turn_id),
        prompt_sha256=digest,
        rationale=_as_str_or_none(rationale),
        provenance_source="declared" if declared_present else "observed",
    )


def sha256_text(text: str) -> str:
    """Return the hex sha256 of ``text`` (used to hash the prompt, not store it)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# -- argument-type normalization (vendor JSON quirks) -------------------------


def coerce_int(value: Any, *, field: str) -> int:
    """Coerce ``value`` to ``int``, accepting stringified ints some clients send.

    Rejects floats with a fractional part and non-numeric strings rather than
    silently truncating — an ambiguous coordinate must surface as an error.
    """
    if isinstance(value, bool):  # bool is an int subclass; reject it explicitly
        raise ValueError(f"{field} must be an integer, got a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ValueError(f"{field} must be a whole number, got {value!r}")
    if isinstance(value, str):
        s = value.strip()
        try:
            return int(s)
        except ValueError as exc:
            raise ValueError(f"{field} must be an integer, got {value!r}") from exc
    raise ValueError(f"{field} must be an integer, got {type(value).__name__}")


def coerce_str(value: Any, *, field: str, allow_none: bool = False) -> Optional[str]:
    """Coerce ``value`` to ``str`` (or ``None`` when allowed)."""
    if value is None:
        if allow_none:
            return None
        raise ValueError(f"{field} is required")
    return str(value)


def _safe_getattr(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name, None)
    except Exception:  # pragma: no cover - never let provenance access raise
        return None


def _as_str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if text else None
