"""Non-native markdown overlay renderer: an inline HTML block redline.

Honesty (read this)
-------------------
Markdown has **no in-file revision concept at all** — a ``.md`` file is plain
text with lightweight markup (``#`` headings, ``-`` list bullets, fenced code).
There is nothing analogous to Word's accept/reject. The review surface is
therefore entirely the ``.changex`` journal plus this projection: an HTML page
showing each block of the document with inserted spans wrapped in ``<ins>`` and
deleted spans in ``<del>``. The journal is the authoritative record; this is a
human-readable lens onto it.

Block granularity
-----------------
ChangeX models a markdown file as a sequence of *blocks* (paragraphs, headings,
list items, code fences) split on blank lines. Each block keeps its raw text
including its markdown markers. The redline therefore shows whole-block context
with the changed text highlighted inline, plus whole inserted/deleted blocks.

This renderer is pure string assembly with HTML-escaping — no network, no I/O.
The md adapter's ``render_tracked()`` returns the bytes of this HTML.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field

_CSS = """
body { font: 14px/1.5 -apple-system, Segoe UI, Roboto, sans-serif; margin: 1.5rem; }
h1 { font-size: 1.35rem; } h2 { font-size: 1rem; margin-top: 1.3rem; }
.block { white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo,
         monospace; border-left: 3px solid #eee; padding: .3rem .6rem; margin: .3rem 0; }
.blockins { border-left-color: #2da44e; background: #f0fff4; }
.blockdel { border-left-color: #cf222e; background: #fff5f5; }
ins { background: #e6ffed; text-decoration: none; }
del { background: #ffeef0; }
.note { color: #666; font-size: .85rem; }
.bnum { color: #888; font-size: .75rem; user-select: none; }
""".strip()

# The honesty note surfaced on the page (and asserted by the adapter docstring).
HONESTY_NOTE = (
    "markdown has no native track-changes; this redline is a projection of the "
    ".changex journal, which is the authoritative record."
)


@dataclass(frozen=True)
class BlockSegment:
    """One contiguous run of a block's text plus its revision tag.

    ``tag`` is one of ``"keep"`` / ``"ins"`` / ``"del"`` — the same vocabulary the
    docx adapter uses internally, projected here to ``<ins>`` / ``<del>`` spans.
    """

    text: str
    tag: str


@dataclass
class BlockRedline:
    """The rendered state of one markdown block for the redline.

    Attributes:
        node_id: The block's stable node_id (e.g. ``"md:00001"``).
        segments: Ordered ``keep`` / ``ins`` / ``del`` segments of the block text.
        inserted: Whole block was added by a ``node.insert``.
        deleted: Whole block was removed by a ``node.delete``.
    """

    node_id: str
    segments: list[BlockSegment] = field(default_factory=list)
    inserted: bool = False
    deleted: bool = False


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _segments_html(segments: list[BlockSegment]) -> str:
    """Render a block's segments as inline ``<ins>`` / ``<del>`` / plain spans."""
    out: list[str] = []
    for seg in segments:
        if not seg.text:
            continue
        if seg.tag == "ins":
            out.append(f"<ins>{_esc(seg.text)}</ins>")
        elif seg.tag == "del":
            out.append(f"<del>{_esc(seg.text)}</del>")
        else:
            out.append(_esc(seg.text))
    return "".join(out)


def _block_html(index: int, block: BlockRedline) -> str:
    """Render one block as a ``<div class="block ...">`` with an inline redline."""
    cls = "block"
    if block.inserted:
        cls += " blockins"
    elif block.deleted:
        cls += " blockdel"
    body = _segments_html(block.segments)
    return (
        f'<div class="{cls}">'
        f'<span class="bnum">{index + 1} &middot; {_esc(block.node_id)}</span>\n'
        f"{body}"
        f"</div>"
    )


def build_redline_html(
    blocks: list[BlockRedline],
    *,
    title: str = "ChangeX Markdown review",
) -> str:
    """Assemble the inline block HTML redline for a markdown journal.

    Args:
        blocks: The ordered blocks with their ``keep`` / ``ins`` / ``del``
            segments (deleted blocks included so the reviewer sees what was cut).
        title: Page title.

    Returns:
        A complete standalone HTML document string. Changed text is wrapped in
        ``<ins>`` / ``<del>``; wholly inserted/deleted blocks are flagged too.
    """
    body = "".join(_block_html(i, block) for i, block in enumerate(blocks))
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body>"
        f"<h1>{_esc(title)}</h1>"
        f'<p class="note">{_esc(HONESTY_NOTE)}</p>'
        "<h2>Block redline</h2>"
        f"{body}"
        "</body></html>"
    )


__all__ = ["BlockSegment", "BlockRedline", "build_redline_html", "HONESTY_NOTE"]
