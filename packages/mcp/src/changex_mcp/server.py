"""The ChangeX stdio FastMCP server.

Wires the six MVP tools (``open_tracked``, ``get_outline``, ``edit``,
``save_tracked``, ``get_changes``, ``render_review``) to the ChangeX core spine.
State is single-process, single-session-per-handle; the journal flushes on every
edit; ``seq`` is server-assigned at apply time.

Provenance is auto-captured where MCP allows (timestamp, session id, transport
request id, and client name/version from the ``clientInfo`` handshake) and
accepted as declared params otherwise (model id / vendor via ``agent_context``,
plus optional rationale / prompt / turn). The prompt is hashed, never stored
verbatim.

Run it with ``python -m changex_mcp`` or ``uvx changex-mcp`` (stdio transport).

The tool *descriptions* below are prompt-engineered: they tell the model to make
the smallest possible edit and never delete-and-reinsert a paragraph for a small
wording change. Combined with the boundary enforcement in :mod:`changex_mcp.tools`
(before-validation + oversized-op rejection), small attributable ops are a
guarantee, not a hope.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP

from changex_mcp import tools
from changex_mcp.provenance import observed_from_mcp
from changex_mcp.session import SessionStore

# The single in-process session registry shared by every tool.
STORE = SessionStore()

mcp = FastMCP(
    "changex",
    instructions=(
        "ChangeX turns your edits to a Word document into native, accept/reject "
        "tracked changes plus a portable, hash-chained provenance journal "
        "(.changex). Workflow: call open_tracked(path) to get a handle, "
        "get_outline(handle) to discover node_ids, then make the SMALLEST "
        "possible edit per call via edit(handle, op=..., node_id=..., ...). "
        "Always pass the exact existing text in `before`; the server validates it "
        "and refuses blind overwrites. Never delete-and-reinsert a whole paragraph "
        "for a small wording change — use replace_text on just the changed words. "
        "Finally call save_tracked(handle, out) to write the Word file and sidecar."
    ),
)


@mcp.tool()
def open_tracked(
    path: str,
    agent_context: Optional[dict[str, Any]] = None,
    author: Optional[str] = None,
) -> dict[str, Any]:
    """Open a .docx for tracked editing; returns {handle, summary, baseline_sha256}.

    Pass agent_context={"model": "<your model id>", "vendor": "<your vendor>"} so
    revisions are authored by your model and attribution is recorded once for the
    whole session. `author` overrides the Word revision author (defaults to the
    model id). This is the first call — every other tool needs the returned handle.
    """
    try:
        return tools.open_tracked(
            STORE, path=path, agent_context=agent_context, author=author
        )
    except tools.ToolError as exc:
        return exc.to_dict()


@mcp.tool()
def get_outline(
    handle: str,
    cursor: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    """List the document's paragraphs (bounded + paginated) to discover node_ids.

    Returns {nodes:[{node_id, kind, preview, style}], next_cursor, total}. Pass the
    returned next_cursor back to page through a large document instead of pulling
    the whole thing into context. Use a node_id from here as the target of `edit`.
    """
    try:
        return tools.get_outline(STORE, handle=handle, cursor=cursor, limit=limit)
    except (tools.ToolError, ValueError) as exc:
        return _coerce_error(exc)


@mcp.tool()
def edit(
    handle: str,
    op: str,
    node_id: str,
    before: Optional[str] = None,
    after: Optional[str] = None,
    anchor: Optional[str] = None,
    text: Optional[str] = None,
    style: Optional[str] = None,
    rationale: Optional[str] = None,
    prompt: Optional[str] = None,
    turn_id: Optional[str] = None,
    ctx: Optional[Context] = None,
) -> dict[str, Any]:
    """Make ONE small tracked edit to a node. Returns {op_id, seq, node_id}.

    Choose `op` and supply only that intent's fields:
      • replace_text       — node_id, before (exact current text), after
      • insert_text_after  — node_id, anchor (exact text to insert after), text
      • delete_text        — node_id, before (exact text to delete)
      • set_paragraph_style— node_id, style (new), before (current style name)

    Rules enforced by the server (not just suggested):
      • `before`/`anchor` must match the node's CURRENT text exactly, or the edit
        is refused (before_mismatch) — this prevents blind overwrites.
      • An op that rewrites >50% of a paragraph is refused with split_required;
        split it into smaller replace_text edits on the specific changed words.
      • Do NOT delete a whole paragraph and re-insert it to change a few words —
        use replace_text on just those words so provenance stays fine-grained.

    `rationale` (why), `prompt`, and `turn_id` are optional declared provenance;
    the prompt is hashed, never stored verbatim. Timestamp, session id, transport
    request id, and your client name/version are captured automatically.
    """
    observed = observed_from_mcp(ctx)
    try:
        return tools.edit(
            STORE,
            handle=handle,
            op=op,
            node_id=node_id,
            before=before,
            after=after,
            anchor=anchor,
            text=text,
            style=style,
            rationale=rationale,
            prompt=prompt,
            turn_id=turn_id,
            observed=observed,
        )
    except (tools.ToolError, ValueError) as exc:
        return _coerce_error(exc)


@mcp.tool()
def save_tracked(handle: str, out: str) -> dict[str, Any]:
    """Write the native-revisions .docx and report the tracked + .changex paths.

    Returns {tracked_path, changex_path, ops, verified}. The .docx has real Word
    accept/reject revisions authored by your model; the .changex is the portable,
    hash-chained provenance journal (already written incrementally on each edit).
    """
    try:
        return tools.save_tracked(STORE, handle=handle, out=out)
    except (tools.ToolError, ValueError) as exc:
        return _coerce_error(exc)


@mcp.tool()
def get_changes(handle: str) -> dict[str, Any]:
    """Return the structured provenance journal: every edit with full attribution.

    Returns {session_id, events:[...], count, verified}. Each event carries the op,
    target node, server-assigned seq, hash, and the observed/declared provenance.
    """
    try:
        return tools.get_changes(STORE, handle=handle)
    except (tools.ToolError, ValueError) as exc:
        return _coerce_error(exc)


@mcp.tool()
def render_review(handle: str, fmt: str = "html") -> dict[str, Any]:
    """Render a human-readable redline of all changes. Returns {format, report}.

    `fmt` is 'html' (default) or 'markdown'. This is the review surface alongside
    the native Word file — it shows what changed, where, and (where known) why/by
    whom, without opening Word.
    """
    try:
        return tools.render_review(STORE, handle=handle, fmt=fmt)
    except (tools.ToolError, ValueError) as exc:
        return _coerce_error(exc)


def _coerce_error(exc: Exception) -> dict[str, Any]:
    """Turn a ToolError or a validation ValueError into a structured error dict."""
    if isinstance(exc, tools.ToolError):
        return exc.to_dict()
    return {"error": "invalid_argument", "detail": str(exc)}


def main() -> None:
    """Console-script / ``python -m changex_mcp`` entry point (stdio transport)."""
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()
