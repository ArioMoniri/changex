"""The md adapter: load -> block model -> apply v0.2 ops -> HTML redline.

Honesty (read this)
-------------------
Markdown (``.md``) has **no in-file revision concept at all** — a ``.md`` file is
plain text with lightweight markup, and there is nothing analogous to Word's
accept/reject. The review surface is therefore entirely the ``.changex`` journal
plus a projected HTML **redline** (inline ``<ins>`` / ``<del>`` per block).
:meth:`render_tracked` returns the bytes of that HTML; :meth:`clean_md_bytes`
returns the shippable plain ``.md`` result of applying the ops. The journal is
authoritative; the redline is a human-readable lens. This mirrors the csv adapter
(also a non-native overlay) rather than the native docx revisions.

Identity strategy
-----------------
A markdown file is modeled as a sequence of *blocks* split on blank lines; each
block keeps its raw text **including** its markdown markers (``#`` headings,
``-``/``*`` list bullets, fenced code, etc.). Blocks get **stable positional
node_ids minted at load** — ``"md:00001"``, ``"md:00002"``, ... — recorded once
so an id survives text edits and sibling insertions (the whole point of
decoupling identity from content). New blocks from ``node.insert`` get a freshly
minted id past the high-water mark.

Revision model
--------------
The adapter tracks, per block, an ordered list of text **segments** tagged
``keep`` / ``ins`` / ``del`` (the same scheme the docx adapter uses). Applying
text ops splits/retags segments at BLOCK granularity; ``node.insert`` /
``node.delete`` add/flag whole blocks. ``render_tracked`` projects the segments
to inline ``<ins>`` / ``<del>`` HTML; ``clean_md_bytes`` joins the current
(keep+ins) text of every non-deleted block with blank-line separators.

Supported ops: ``text.insert``, ``text.delete``, ``text.replace``,
``node.insert``, ``node.delete``. Spreadsheet/slide ops are not meaningful for
markdown and are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from changex_core.adapters.base import (
    BeforeMismatchError,
    DocumentAdapter,
    NodeNotFoundError,
    OversizedOpError,
)
from changex_core.journal.canonical import sha256_hex
from changex_core.model.nodes import Node, NodeKind
from changex_core.ops.vocabulary import (
    NodeDelete,
    NodeInsert,
    Op,
    TextDelete,
    TextInsert,
    TextReplace,
)
from changex_core.paths import safe_path
from changex_core.render.md import BlockRedline, BlockSegment, build_redline_html

# An op may not rewrite more than this fraction of a block's text in one go
# (mirrors the docx adapter's oversized-op guard).
MAX_OP_FRACTION = 0.5
DEFAULT_AUTHOR = "ChangeX agent"
DEFAULT_DATE = "2026-06-02T00:00:00Z"
NODE_ID_PREFIX = "md"


@dataclass
class _Segment:
    """One contiguous text segment within a block and its revision tag."""

    text: str
    tag: str  # "keep" | "ins" | "del"


@dataclass
class _Block:
    """Adapter-side state for one markdown block (model + revision segments)."""

    node_id: str
    segments: list[_Segment] = field(default_factory=list)
    inserted: bool = False  # whole block is a node.insert
    deleted: bool = False  # whole block is a node.delete

    def current_text(self) -> str:
        """Text as it stands now (keep + ins segments; del removed)."""
        return "".join(s.text for s in self.segments if s.tag != "del")

    def baseline_text(self) -> str:
        """Text in the baseline (keep + del segments; ins removed)."""
        return "".join(s.text for s in self.segments if s.tag != "ins")


class MdAdapter(DocumentAdapter):
    """Loads a .md, applies v0.2 block/text ops, renders an HTML redline overlay.

    Markdown has no native revisions; the journal is the source of truth and
    :meth:`render_tracked` projects it as an inline ``<ins>`` / ``<del>`` block
    redline (a non-native overlay, like csv).
    """

    def __init__(
        self,
        raw_bytes: bytes,
        *,
        author: str = DEFAULT_AUTHOR,
        date: str = DEFAULT_DATE,
    ) -> None:
        self._raw = raw_bytes
        self._author = author
        self._date = date
        self._baseline_sha = sha256_hex(raw_bytes)
        self._blocks: list[_Block] = []
        self._seq = 0
        self._build_model(raw_bytes)

    # -- construction ---------------------------------------------------------

    @classmethod
    def load(
        cls,
        path: str,
        *,
        author: str = DEFAULT_AUTHOR,
        date: str = DEFAULT_DATE,
        **_: Any,
    ) -> "MdAdapter":
        """Load a .md from a sanitized path (extra kwargs are accepted+ignored)."""
        resolved = safe_path(path, must_exist=True, allow_suffixes=(".md",))
        raw = resolved.read_bytes()
        return cls(raw, author=author, date=date)

    def _mint_node_id(self) -> str:
        """Mint the next stable positional block id (``md:00001``, ...)."""
        self._seq += 1
        return f"{NODE_ID_PREFIX}:{self._seq:05d}"

    @staticmethod
    def _split_blocks(text: str) -> list[str]:
        """Split markdown ``text`` into blocks on runs of blank lines.

        A block keeps its raw lines (incl. heading/list markers) joined by ``\\n``.
        Lines that are empty or whitespace-only delimit blocks; leading/trailing
        blank runs are dropped so the block list is the document's content blocks.
        """
        blocks: list[str] = []
        current: list[str] = []
        for line in text.splitlines():
            if line.strip() == "":
                if current:
                    blocks.append("\n".join(current))
                    current = []
            else:
                current.append(line)
        if current:
            blocks.append("\n".join(current))
        return blocks

    def _build_model(self, raw: bytes) -> None:
        text = raw.decode("utf-8")
        self._blocks = []
        self._seq = 0
        for block_text in self._split_blocks(text):
            self._blocks.append(
                _Block(
                    node_id=self._mint_node_id(),
                    segments=[_Segment(text=block_text, tag="keep")] if block_text else [],
                )
            )

    # -- DocumentAdapter contract --------------------------------------------

    def baseline_sha256(self) -> str:
        return self._baseline_sha

    def to_model(self) -> Node:
        """Return the model tree: root -> one PARAGRAPH node per (live) block."""
        root = Node(node_id="root", node_kind=NodeKind.DOCUMENT, path="/md")
        for idx, block in enumerate(self._blocks):
            if block.deleted:
                continue
            root.children.append(
                Node(
                    node_id=block.node_id,
                    node_kind=NodeKind.PARAGRAPH,
                    path=f"/md/block[{idx + 1}]",
                    value=block.current_text(),
                    attrs={"index": idx},
                )
            )
        return root

    def set_model(self, root: Node) -> None:
        """Reset adapter state to ``root`` (used by :meth:`Journal.replay`)."""
        self._blocks = []
        self._seq = 0
        for pnode in root.child_paragraphs():
            text = str(pnode.value or "")
            node_id = pnode.node_id or self._mint_node_id()
            self._track_seq(node_id)
            self._blocks.append(
                _Block(
                    node_id=node_id,
                    segments=[_Segment(text=text, tag="keep")] if text else [],
                )
            )

    def _track_seq(self, node_id: str) -> None:
        """Keep ``self._seq`` past any numeric suffix so new mints never collide."""
        prefix = f"{NODE_ID_PREFIX}:"
        if node_id.startswith(prefix):
            tail = node_id[len(prefix) :]
            if tail.isdigit():
                self._seq = max(self._seq, int(tail))

    def resolve(self, node_id: str) -> Node | None:
        return self.to_model().find(node_id)

    def _block(self, node_id: str) -> _Block:
        for block in self._blocks:
            if block.node_id == node_id and not block.deleted:
                return block
        raise NodeNotFoundError(f"no block with node_id {node_id!r}")

    # -- apply ----------------------------------------------------------------

    def apply(self, op: Op) -> None:
        """Apply one v0.2 markdown op (validating before-substring and op size)."""
        if isinstance(op, TextReplace):
            self._apply_replace(op)
        elif isinstance(op, TextInsert):
            self._apply_insert(op)
        elif isinstance(op, TextDelete):
            self._apply_delete(op)
        elif isinstance(op, NodeInsert):
            self._apply_node_insert(op)
        elif isinstance(op, NodeDelete):
            self._apply_node_delete(op)
        else:  # pragma: no cover - exhaustive over supported md ops
            raise TypeError(
                f"unsupported op type {type(op).__name__} for markdown "
                "(cell/row/slide/style ops are not meaningful for md)"
            )

    def _check_size(self, block: _Block, changed_len: int) -> None:
        current = len(block.current_text())
        if current and changed_len > current * MAX_OP_FRACTION:
            raise OversizedOpError(
                "split_required: this op rewrites more than "
                f"{int(MAX_OP_FRACTION * 100)}% of the block; split it into "
                "smaller edits and re-issue them."
            )

    def _locate(self, block: _Block, needle: str) -> tuple[int, int]:
        """Return (segment_index, offset) where ``needle`` starts in a kept run.

        Searches current (keep+ins) text but resolves to a single splittable
        segment. Raises :class:`BeforeMismatchError` on mismatch (the guard).
        """
        if needle == "":
            raise BeforeMismatchError("before/anchor must be non-empty")
        for i, seg in enumerate(block.segments):
            if seg.tag == "del":
                continue
            start = seg.text.find(needle)
            if start != -1:
                return i, start
        raise BeforeMismatchError(
            f"before text {needle!r} not found in node {block.node_id!r}"
        )

    def _split_segment(self, block: _Block, seg_idx: int, start: int, length: int) -> int:
        """Split the segment at ``seg_idx`` so [start, start+length) is isolated.

        Returns the index of the isolated middle segment.
        """
        seg = block.segments[seg_idx]
        before = seg.text[:start]
        middle = seg.text[start : start + length]
        after = seg.text[start + length :]
        replacement: list[_Segment] = []
        if before:
            replacement.append(_Segment(before, seg.tag))
        replacement.append(_Segment(middle, seg.tag))
        if after:
            replacement.append(_Segment(after, seg.tag))
        block.segments[seg_idx : seg_idx + 1] = replacement
        return seg_idx + (1 if before else 0)

    def _apply_replace(self, op: TextReplace) -> None:
        block = self._block(op.node_id)
        self._check_size(block, max(len(op.before), len(op.after)))
        seg_idx, start = self._locate(block, op.before)
        mid = self._split_segment(block, seg_idx, start, len(op.before))
        block.segments[mid].tag = "del"
        block.segments.insert(mid + 1, _Segment(op.after, "ins"))

    def _apply_delete(self, op: TextDelete) -> None:
        block = self._block(op.node_id)
        self._check_size(block, len(op.before))
        seg_idx, start = self._locate(block, op.before)
        mid = self._split_segment(block, seg_idx, start, len(op.before))
        block.segments[mid].tag = "del"

    def _apply_insert(self, op: TextInsert) -> None:
        block = self._block(op.node_id)
        self._check_size(block, len(op.text))
        if op.before_anchor is None:
            block.segments.append(_Segment(op.text, "ins"))
            return
        seg_idx, start = self._locate(block, op.before_anchor)
        # insert AFTER the anchor occurrence
        mid = self._split_segment(block, seg_idx, start, len(op.before_anchor))
        block.segments.insert(mid + 1, _Segment(op.text, "ins"))

    def _apply_node_insert(self, op: NodeInsert) -> None:
        text = str(op.value.get("text", ""))
        new_block = _Block(
            node_id=self._mint_node_id(),
            inserted=True,
            segments=[_Segment(text, "ins")] if text else [],
        )
        pos = max(0, min(op.position, len(self._blocks)))
        self._blocks.insert(pos, new_block)

    def _apply_node_delete(self, op: NodeDelete) -> None:
        block = self._block(op.node_id)
        block.deleted = True
        for seg in block.segments:
            if seg.tag == "keep":
                seg.tag = "del"

    # -- render / save --------------------------------------------------------

    def _block_redlines(self) -> list[BlockRedline]:
        """Project the adapter blocks to render-layer :class:`BlockRedline`s."""
        out: list[BlockRedline] = []
        for block in self._blocks:
            out.append(
                BlockRedline(
                    node_id=block.node_id,
                    segments=[BlockSegment(s.text, s.tag) for s in block.segments],
                    inserted=block.inserted,
                    deleted=block.deleted,
                )
            )
        return out

    def render_tracked(self) -> bytes:
        """Return the inline ``<ins>`` / ``<del>`` block HTML redline bytes.

        Markdown has no native track-changes, so this projection of the journal
        *is* the review surface. The clean markdown is available via
        :meth:`clean_md_bytes`.
        """
        return build_redline_html(self._block_redlines()).encode("utf-8")

    def clean_md_bytes(self) -> bytes:
        """Return the CLEAN shippable ``.md`` bytes (no redline markup).

        Blocks are joined with a blank line between them and the document ends
        with a trailing newline (the conventional shape of a markdown file).
        """
        texts = [
            block.current_text() for block in self._blocks if not block.deleted
        ]
        body = "\n\n".join(t for t in texts if t)
        if body:
            body += "\n"
        return body.encode("utf-8")

    def save(self, out_path: str) -> None:
        """Save the clean ``.md`` and a sibling ``<name>.review.html`` redline.

        ``out_path`` keeps the ``.md`` extension (so the CLI's same-extension rule
        holds); the redline HTML is written next to it as ``<name>.review.html``.
        """
        resolved = safe_path(out_path, allow_suffixes=(".md",))
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_bytes(self.clean_md_bytes())
        review = resolved.with_suffix(".review.html")
        review.write_bytes(self.render_tracked())

    # -- accessors ------------------------------------------------------------

    def node_id_map(self) -> dict[str, str]:
        """md addresses by positional minted id, so there is no carrier map."""
        return {}
