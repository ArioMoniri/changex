"""The MCP tool implementations, decoupled from FastMCP registration.

These are plain typed functions that operate on a :class:`SessionStore`, so they
are unit-testable in-process without a transport. ``server.py`` wraps each one as
a FastMCP tool, threading the call ``Context`` through for observed provenance.

Boundary enforcement (the product-risk mitigation) lives here, not in prompting:

* Every text edit carries the exact ``before`` substring; the core adapter
  validates it against the node's *current* content and raises
  :class:`BeforeMismatchError` on mismatch — blind full-node overwrites are
  refused.
* The adapter raises :class:`OversizedOpError` (``split_required: ...``) when one
  op rewrites more than half a node; we surface that structured message so the
  *error itself is the prompt* telling the model to split the change.

The single ``edit`` tool is intent-dispatched on an ``op`` discriminator
(``replace_text`` / ``insert_text_after`` / ``delete_text`` /
``set_paragraph_style``) so the model still picks a narrow intent and the typed
payload per intent is enforced, while the client only sees one edit verb.
"""

from __future__ import annotations

from typing import Any, Optional

from changex_core.adapters.base import (
    BeforeMismatchError,
    NodeNotFoundError,
    OversizedOpError,
)
from changex_core.journal.events import Target
from changex_core.ops.vocabulary import (
    Op,
    StyleChange,
    TextDelete,
    TextInsert,
    TextReplace,
    target_node_id,
)
from changex_core.paths import safe_path
from changex_core.render.html import render_html, render_markdown

from changex_mcp.outline import build_outline
from changex_mcp.provenance import (
    AgentContext,
    ObservedContext,
    build_provenance,
    coerce_int,
    coerce_str,
)
from changex_mcp.session import Session, SessionError, SessionStore

# Intent discriminators accepted by the polymorphic ``edit`` tool.
EDIT_OPS = ("replace_text", "insert_text_after", "delete_text", "set_paragraph_style")


class ToolError(Exception):
    """A structured, client-facing tool error.

    ``code`` is a stable machine-readable tag (e.g. ``split_required``,
    ``before_mismatch``) and ``message`` is the human/agent-facing instruction.
    The message for ``split_required`` is deliberately prescriptive: it is the
    prompt that nudges the model toward smaller edits.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.code, "detail": self.message}


# -- open / outline -----------------------------------------------------------


def open_tracked(
    store: SessionStore,
    *,
    path: str,
    agent_context: Optional[dict[str, Any]] = None,
    author: Optional[str] = None,
) -> dict[str, Any]:
    """Open a .docx for tracked editing and return a session handle + summary.

    ``agent_context={model, vendor}`` is captured **once** here (labeled
    ``provenance_source='declared'`` downstream); the model id is also used as the
    Word revision author so accepted revisions are attributed to the model.
    """
    ctx = AgentContext.from_obj(agent_context)
    revision_author = author or ctx.agent or "ChangeX agent"
    try:
        session = store.open(
            source_path=path,
            changex_path=None,
            agent_context=ctx,
            author=revision_author,
        )
    except SessionError as exc:
        # e.g. the same document is already open in this single-session server.
        raise ToolError("already_open", str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise ToolError("open_failed", str(exc)) from exc

    model = session.adapter.to_model()
    summary = {
        "filename": session.source_path.name,
        "paragraphs": len(model.child_paragraphs()),
        "agent": ctx.agent,
        "vendor": ctx.vendor,
        "changex_path": str(session.changex_path),
    }
    return {
        "handle": session.handle,
        "summary": summary,
        "baseline_sha256": session.adapter.baseline_sha256(),
        "session_id": session.session_id,
    }


def get_outline(
    store: SessionStore,
    *,
    handle: str,
    cursor: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Return a bounded, paginated outline of the open document's paragraphs."""
    session = store.get(handle)
    limit_int = coerce_int(limit, field="limit")
    page = build_outline(session.adapter.to_model(), cursor=cursor, limit=limit_int)
    return page.to_dict()


# -- edit (intent-dispatched) -------------------------------------------------


def edit(
    store: SessionStore,
    *,
    handle: str,
    op: str,
    node_id: str,
    before: Optional[str] = None,
    after: Optional[str] = None,
    anchor: Optional[str] = None,
    text: Optional[str] = None,
    style: Optional[str] = None,
    rationale: Optional[str] = None,
    observed: Optional[ObservedContext] = None,
    prompt: Optional[str] = None,
    prompt_sha256: Optional[str] = None,
    turn_id: Optional[str] = None,
) -> dict[str, Any]:
    """Apply one small, intent-named edit to a node and journal it.

    ``op`` selects the intent and the required payload:

    * ``replace_text``       — ``node_id``, ``before``, ``after``
    * ``insert_text_after``  — ``node_id``, ``anchor`` (or ``before``), ``text``
    * ``delete_text``        — ``node_id``, ``before``
    * ``set_paragraph_style``— ``node_id``, ``style``, ``before`` (current style)

    Validates the ``before`` substring and op size at the boundary, assigns a
    server-side monotonic ``seq``, and flushes the journal — all under the
    session lock so concurrent calls are race-free.
    """
    session = store.get(handle)
    op_name = coerce_str(op, field="op")
    if op_name not in EDIT_OPS:
        raise ToolError(
            "unknown_op",
            f"op must be one of {EDIT_OPS}; got {op_name!r}.",
        )
    node_id_str = coerce_str(node_id, field="node_id") or ""
    core_op = _build_op(op_name, node_id_str, before, after, anchor, text, style)

    obs = observed or ObservedContext()
    provenance = build_provenance(
        session_id=session.session_id,
        observed=obs,
        agent_context=session.agent_context,
        rationale=coerce_str(rationale, field="rationale", allow_none=True),
        prompt=coerce_str(prompt, field="prompt", allow_none=True),
        prompt_sha256=coerce_str(prompt_sha256, field="prompt_sha256", allow_none=True),
        turn_id=coerce_str(turn_id, field="turn_id", allow_none=True),
    )

    # Serialize apply + append so seq is monotonic and the journal never sees a
    # half-applied op under concurrent tool calls in one turn.
    with session.lock:
        try:
            session.adapter.apply(core_op)
        except OversizedOpError as exc:
            raise ToolError("split_required", str(exc)) from exc
        except BeforeMismatchError as exc:
            raise ToolError("before_mismatch", str(exc)) from exc
        except NodeNotFoundError as exc:
            raise ToolError("node_not_found", str(exc)) from exc
        target = _target_for(session, core_op, node_id_str)
        event = session.journal.append(core_op, target, provenance)

    return {
        "op_id": event.op_id,
        "seq": event.seq,
        "node_id": target.node_id,
        "provenance_source": provenance.provenance_source,
    }


def _build_op(
    op_name: str,
    node_id: str,
    before: Optional[str],
    after: Optional[str],
    anchor: Optional[str],
    text: Optional[str],
    style: Optional[str],
) -> Op:
    """Construct the typed core op for an intent, validating required fields."""
    if op_name == "replace_text":
        _require(before, "before", op_name)
        _require(after, "after", op_name)
        return TextReplace(node_id=node_id, before=str(before), after=str(after))
    if op_name == "delete_text":
        _require(before, "before", op_name)
        return TextDelete(node_id=node_id, before=str(before))
    if op_name == "insert_text_after":
        _require(text, "text", op_name)
        # Accept `anchor` (preferred) or fall back to `before`; None => append.
        anchor_val = anchor if anchor is not None else before
        return TextInsert(
            node_id=node_id,
            before_anchor=str(anchor_val) if anchor_val is not None else None,
            text=str(text),
        )
    if op_name == "set_paragraph_style":
        _require(style, "style", op_name)
        _require(before, "before", op_name)
        return StyleChange(node_id=node_id, style=str(style), before=str(before))
    raise ToolError("unknown_op", f"unsupported op {op_name!r}")  # pragma: no cover


def _require(value: Any, field: str, op_name: str) -> None:
    if value is None or value == "":
        raise ToolError(
            "missing_field",
            f"{op_name} requires a non-empty {field!r}.",
        )


def _target_for(session: Session, op: Op, fallback_node_id: str) -> Target:
    """Build a journal :class:`Target` from the op's resolved model node."""
    node_id = target_node_id(op) or fallback_node_id
    node = session.adapter.resolve(node_id)
    return Target(
        node_id=node_id,
        node_kind=(node.node_kind.value if node else "paragraph"),
        path=(node.path if node else ""),
    )


# -- save / changes / review --------------------------------------------------


def save_tracked(
    store: SessionStore,
    *,
    handle: str,
    out: str,
) -> dict[str, Any]:
    """Save the native-revisions .docx and report the tracked + .changex paths.

    The journal is already persisted incrementally; here we just write the Word
    file and verify the chain before reporting success.
    """
    session = store.get(handle)
    out_path = safe_path(out, allow_suffixes=(".docx",))
    with session.lock:
        session.adapter.save(str(out_path))
        verify = session.journal.verify()
    return {
        "tracked_path": str(out_path),
        "changex_path": str(session.changex_path),
        "ops": session.journal.last_seq,
        "verified": verify.ok,
    }


def get_changes(store: SessionStore, *, handle: str) -> dict[str, Any]:
    """Return the structured provenance journal (active, non-reverted events)."""
    session = store.get(handle)
    events = [event.to_dict() for event in session.journal.active_events()]
    verify = session.journal.verify()
    return {
        "session_id": session.session_id,
        "events": events,
        "count": len(events),
        "verified": verify.ok,
    }


def render_review(
    store: SessionStore,
    *,
    handle: str,
    fmt: str = "html",
) -> dict[str, Any]:
    """Render an HTML or markdown redline of the journal for human review."""
    session = store.get(handle)
    fmt_norm = (coerce_str(fmt, field="fmt") or "html").lower()
    if fmt_norm not in ("html", "markdown"):
        raise ToolError("bad_format", "fmt must be 'html' or 'markdown'.")
    events = session.journal.active_events()
    report = render_markdown(events) if fmt_norm == "markdown" else render_html(events)
    return {"format": fmt_norm, "report": report}
