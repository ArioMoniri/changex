"""Bounded, paginated document outline so large docs don't blow model context.

``get_outline`` returns a slice of the document's paragraph nodes — each entry is
``{node_id, kind, preview, style}`` — plus an opaque ``next_cursor`` the model
passes back to page forward. The model uses the returned ``node_id``s to target
the ``edit`` tool, so the outline is the discovery surface for addressing.

Previews are truncated to keep the payload small — enough to *locate* a paragraph,
not to edit it. To change wording past the preview, an agent reads the paragraph's
full current text with the ``read_node`` tool first, then supplies an exact ``before``
substring on edit (which the adapter validates).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from changex_core.model.nodes import Node

PREVIEW_CHARS = 120
DEFAULT_LIMIT = 100
MAX_LIMIT = 500


@dataclass
class OutlineEntry:
    """One node in a paginated outline page.

    ``truncated`` / ``chars`` tell the agent whether ``preview`` is the whole
    paragraph or just its opening — when ``truncated`` is true, ``read_node`` is
    required before editing wording it can't see in ``preview``.
    """

    node_id: str
    kind: str
    preview: str
    style: Optional[str] = None
    truncated: bool = False
    chars: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "preview": self.preview,
            "style": self.style,
            "truncated": self.truncated,
            "chars": self.chars,
        }


@dataclass
class OutlinePage:
    """A bounded outline page plus the cursor to fetch the next one."""

    nodes: list[OutlineEntry]
    next_cursor: Optional[str]
    total: int

    def to_dict(self) -> dict[str, object]:
        page: dict[str, object] = {
            "nodes": [n.to_dict() for n in self.nodes],
            "next_cursor": self.next_cursor,
            "total": self.total,
        }
        # Make the truncation impossible to miss: if ANY preview is clipped, tell the
        # agent — in the tool result itself — how to read the rest before it edits.
        if any(n.truncated for n in self.nodes):
            page["note"] = (
                "Some previews are truncated (each node has `truncated` and the full "
                "`chars` count). The preview is enough to LOCATE a paragraph, not to "
                "edit it — before changing any wording you can't fully see, call "
                "read_node(handle, node_id) to read the paragraph's full current text "
                "and copy an exact `before` from it. Never guess clipped text."
            )
        return page


def _preview(text: str) -> tuple[str, bool]:
    """Collapse and truncate ``text`` for a compact preview.

    Returns ``(preview, truncated)``. Truncation lands on a word boundary (so the
    preview never ends mid-word like ``"…produce a v"``) and is flagged with a
    trailing ``" …"`` — the caller also exposes the full ``chars`` count so the
    agent knows there is more to read via ``read_node``.
    """
    flat = " ".join((text or "").split())
    if len(flat) <= PREVIEW_CHARS:
        return flat, False
    cut = flat[: PREVIEW_CHARS - 2]
    sp = cut.rfind(" ")
    if sp >= PREVIEW_CHARS // 2:  # only honor the boundary if it isn't absurdly early
        cut = cut[:sp]
    return cut.rstrip() + " …", True


def _decode_cursor(cursor: Optional[str]) -> int:
    """Parse the opaque cursor into a start offset (defaults to 0)."""
    if not cursor:
        return 0
    try:
        offset = int(cursor)
    except (TypeError, ValueError):
        return 0
    return max(0, offset)


def build_outline(
    model: Node,
    *,
    cursor: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
) -> OutlinePage:
    """Return a bounded page of the model's paragraph nodes.

    Args:
        model: The current document model root.
        cursor: Opaque pagination cursor from a previous page (or ``None``).
        limit: Max entries per page (clamped to ``[1, MAX_LIMIT]``).

    Returns:
        An :class:`OutlinePage` with ``next_cursor`` set when more remain.
    """
    paras = model.child_paragraphs()
    total = len(paras)
    limit = max(1, min(int(limit), MAX_LIMIT))
    start = _decode_cursor(cursor)
    window = paras[start : start + limit]

    entries: list[OutlineEntry] = []
    for node in window:
        full = node.text() or str(node.value or "")
        preview, truncated = _preview(full)
        entries.append(
            OutlineEntry(
                node_id=node.node_id,
                kind=node.node_kind.value,
                preview=preview,
                style=str(node.attrs.get("style")) if node.attrs.get("style") else None,
                truncated=truncated,
                chars=len(full),
            )
        )
    next_index = start + limit
    next_cursor = str(next_index) if next_index < total else None
    return OutlinePage(nodes=entries, next_cursor=next_cursor, total=total)
