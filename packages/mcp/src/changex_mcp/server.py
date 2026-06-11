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
Pass ``--http`` (see :mod:`changex_mcp.transport`) to instead serve a remote
Streamable HTTP transport for connector-URL clients (claude.ai custom connectors,
ChatGPT app connectors), guarded by a loopback-default + bearer-token policy.

The tool *descriptions* below are prompt-engineered: they tell the model to make
the smallest possible edit and never delete-and-reinsert a paragraph for a small
wording change. Combined with the boundary enforcement in :mod:`changex_mcp.tools`
(before-validation + oversized-op rejection), small attributable ops are a
guarantee, not a hope.
"""

from __future__ import annotations

import sys
from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP

from changex_mcp import tools, transport
from changex_mcp.provenance import observed_from_mcp
from changex_mcp.session import SessionStore

# The single in-process session registry shared by every tool.
STORE = SessionStore()

_INSTRUCTIONS = (
    "ChangeX turns your edits to a Word document into native, accept/reject "
    "tracked changes plus a portable, hash-chained provenance journal "
    "(.changex). Workflow: call open_tracked(path) to get a handle, "
    "get_outline(handle) to discover node_ids. The outline's `preview` is "
    "truncated (~120 chars), so to change wording anywhere past the opening of a "
    "paragraph, call read_node(handle, node_id) to read its FULL current text and "
    "copy the exact `before` from it — never guess text you cannot see. Then make "
    "the SMALLEST possible edit per call via edit(handle, op=..., node_id=..., ...). "
    "Always pass the exact existing text in `before`; the server validates it "
    "and refuses blind overwrites. Never delete-and-reinsert a whole paragraph "
    "for a small wording change — use replace_text on just the changed words. "
    "Finally call save_tracked(handle, out) to write the Word file and sidecar."
)


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


def get_outline(
    handle: str,
    cursor: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    """List the document's paragraphs (bounded + paginated) to discover node_ids.

    Returns {nodes:[{node_id, kind, preview, style}], next_cursor, total}. Pass the
    returned next_cursor back to page through a large document instead of pulling
    the whole thing into context. Use a node_id from here as the target of `edit`.

    NOTE: `preview` is TRUNCATED (~120 chars). It is enough to identify a paragraph,
    NOT enough to safely edit past the opening — to change wording in the middle or end
    of a paragraph, call read_node(handle, node_id) first to read its full current text.
    """
    try:
        return tools.get_outline(STORE, handle=handle, cursor=cursor, limit=limit)
    except (tools.ToolError, ValueError) as exc:
        return _coerce_error(exc)


def read_node(handle: str, node_id: str) -> dict[str, Any]:
    """Read the FULL current text of one paragraph, so you can edit its middle or end.

    Returns {node_id, kind, style, text, length}. `get_outline` only gives a short,
    truncated `preview` of each paragraph — so you literally cannot see (and must not
    guess) text beyond the first ~120 characters. Before ANY replace_text / delete_text /
    insert_text_after that targets wording you can't fully see in the preview, call
    read_node(handle, node_id), then copy the exact `before` substring out of the returned
    `text`. That `text` is precisely what the edit guard matches `before` against, so a
    substring of it always matches — no blind edits, no broken clinical/legal details.
    """
    try:
        return tools.read_node(STORE, handle=handle, node_id=node_id)
    except (tools.ToolError, ValueError) as exc:
        return _coerce_error(exc)


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


def reject(handle: str, op_id: str) -> dict[str, Any]:
    """Reject a change by op_id so its revision is dropped from the saved .docx.

    Returns {op_id, status, reverted, active_ops, verified}. This is the human/
    agent review gate: a rejected op is non-destructively reverted in the journal
    (the rejection is itself audited) and excluded from the next save_tracked, so
    its tracked-change revision is genuinely absent from the rendered Word file.
    Use accept(handle, op_id) to restore it. Reverting twice is a no-op.
    """
    try:
        return tools.reject(STORE, handle=handle, op_id=op_id)
    except (tools.ToolError, ValueError) as exc:
        return _coerce_error(exc)


def accept(handle: str, op_id: str) -> dict[str, Any]:
    """Accept (un-reject) a previously rejected change so its revision is kept.

    Returns {op_id, status, reverted, active_ops, verified}. The accept side of
    review: it un-reverts the op (also audited) so it rejoins the active set and
    its revision reappears in the next save_tracked. Accepting an op that was
    never rejected is a no-op.
    """
    try:
        return tools.accept(STORE, handle=handle, op_id=op_id)
    except (tools.ToolError, ValueError) as exc:
        return _coerce_error(exc)


def get_changes(handle: str) -> dict[str, Any]:
    """Return the structured provenance journal: every edit with full attribution.

    Returns {session_id, events:[...], count, verified}. Each event carries the op,
    target node, server-assigned seq, hash, and the observed/declared provenance.
    """
    try:
        return tools.get_changes(STORE, handle=handle)
    except (tools.ToolError, ValueError) as exc:
        return _coerce_error(exc)


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


# The tool callables, registered identically on every FastMCP instance.
_TOOLS = (
    open_tracked,
    get_outline,
    read_node,
    edit,
    save_tracked,
    reject,
    accept,
    get_changes,
    render_review,
)


def build_mcp() -> FastMCP:
    """Build a fresh, fully-configured :class:`FastMCP` with all ChangeX tools.

    A factory (rather than a single module global) is needed because the SDK's
    Streamable-HTTP session manager can only be started once per ``FastMCP``
    instance, so each HTTP server build must get its own. The stdio path uses the
    shared module-level :data:`mcp` singleton, unchanged.
    """
    app = FastMCP("changex", instructions=_INSTRUCTIONS)
    for fn in _TOOLS:
        app.tool()(fn)
    return app


# The shared singleton used by the stdio transport (behavior unchanged).
mcp = build_mcp()


def main(argv: Optional[list[str]] = None) -> None:
    """Console-script / ``python -m changex_mcp`` entry point.

    Default (no args) keeps the unchanged local **stdio** transport. With
    ``--http`` / ``--sse`` (or ``CHANGEX_MCP_TRANSPORT=http``) it serves the
    remote HTTP transport that connector-URL clients dial — subject to the
    loopback-default + bearer-token bind policy in :mod:`changex_mcp.transport`.
    """
    try:
        settings = transport.build_settings(argv)
    except transport.TransportConfigError as exc:
        # The insecure-bind warning was already printed to stderr by the policy.
        print(f"[changex-mcp] {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    if settings.transport == "stdio":
        mcp.run()  # unchanged local stdio path
    else:
        # A dedicated instance for the HTTP server: its Streamable-HTTP session
        # manager may only start once, so never reuse the stdio singleton.
        transport.serve_http(build_mcp(), settings)


if __name__ == "__main__":  # pragma: no cover
    main()
