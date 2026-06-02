"""difflib-based, paragraph-level op reconstruction (passive ``seal`` path).

The reconstruction is two-level and deliberately coarse:

1. **Paragraph alignment** — :class:`difflib.SequenceMatcher` over the *baseline*
   vs *current* paragraph text sequences yields a block opcode stream. ``equal``
   blocks pair paragraphs 1:1 (and may still differ in text/style); ``replace``
   pairs aligned slices; ``delete`` blocks are removed paragraphs and ``insert``
   blocks are added paragraphs.
2. **Intra-paragraph diff** — for an aligned pair whose text differs, a second
   :class:`difflib.SequenceMatcher` (this time over characters) collapses the
   per-position opcodes into a single best-effort ``text.replace`` /
   ``text.insert`` / ``text.delete`` for the changed span. We emit one op per
   changed paragraph rather than many micro-ops: passive reconstruction cannot
   recover real intent, so a smaller, honest op set is preferable to a noisy one.

Nothing here fabricates provenance — these are *observations* of the net textual
delta, mapped onto the frozen v0.1 op vocabulary. Identity is best-effort: an
aligned paragraph keeps its baseline ``node_id``; added paragraphs get
``node.insert`` (no stable id yet) and removed ones ``node.delete``.

Pure stdlib (:mod:`difflib`); no document parsing happens here — callers pass in
already-extracted paragraph tuples (see :mod:`changex_core.passive`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Optional


@dataclass(frozen=True)
class ParagraphSpec:
    """One extracted paragraph: stable id (if known), text, and style name."""

    node_id: Optional[str]
    text: str
    style: str = "Normal"


@dataclass(frozen=True)
class ReconstructedOp:
    """A single op dict reconstructed by the passive diff, plus its target.

    ``op`` is a frozen-v0.1 op dict (parseable by ``op_from_dict``). ``node_id``
    is the target paragraph id for text/style/node.delete ops, or ``None`` for a
    ``node.insert`` (which addresses by position, not id). ``node_kind`` is always
    ``"paragraph"`` for the v0.1 docx surface.
    """

    op: dict[str, Any]
    node_id: Optional[str]
    node_kind: str = "paragraph"


@dataclass
class ParagraphDiff:
    """The structured result of diffing two paragraph sequences."""

    ops: list[ReconstructedOp] = field(default_factory=list)
    replaced: int = 0
    inserted: int = 0
    deleted: int = 0
    style_changed: int = 0

    @property
    def total(self) -> int:
        return len(self.ops)


def _intra_paragraph_op(
    node_id: Optional[str], before: str, after: str
) -> Optional[ReconstructedOp]:
    """Reduce a changed paragraph to ONE coarse text op over its changed span.

    Returns ``None`` if the texts are identical. Uses the outermost changed
    region (first divergence to last) so a single ``text.replace`` / insert /
    delete captures the net delta honestly without exploding into micro-ops.
    """
    if before == after:
        return None

    matcher = SequenceMatcher(a=before, b=after, autojunk=False)
    opcodes = [oc for oc in matcher.get_opcodes() if oc[0] != "equal"]
    if not opcodes:  # pragma: no cover - defensive; before != after implies some
        return None

    # Outermost changed window: from the first changed char to the last, on both
    # sides. Collapsing to one span keeps the reconstruction coarse + honest.
    a_lo = min(oc[1] for oc in opcodes)
    a_hi = max(oc[2] for oc in opcodes)
    b_lo = min(oc[3] for oc in opcodes)
    b_hi = max(oc[4] for oc in opcodes)

    removed = before[a_lo:a_hi]
    added = after[b_lo:b_hi]

    if removed and added:
        op = {
            "kind": "text.replace",
            "node_id": node_id or "",
            "before": removed,
            "after": added,
        }
    elif removed:
        op = {"kind": "text.delete", "node_id": node_id or "", "before": removed}
    else:
        # Pure insertion. Anchor on the char just before the inserted span so the
        # op is replayable; ``None`` anchor means append-at-end.
        anchor = before[:a_lo][-1:] or None
        op = {
            "kind": "text.insert",
            "node_id": node_id or "",
            "before_anchor": anchor,
            "text": added,
        }
    return ReconstructedOp(op=op, node_id=node_id)


def _style_op(spec_before: ParagraphSpec, spec_after: ParagraphSpec) -> Optional[ReconstructedOp]:
    """Emit a ``style.change`` op when an aligned paragraph's style differs."""
    if spec_before.style == spec_after.style or not spec_after.style:
        return None
    op = {
        "kind": "style.change",
        "node_id": spec_before.node_id or "",
        "style": spec_after.style,
        "before": spec_before.style,
    }
    return ReconstructedOp(op=op, node_id=spec_before.node_id)


def _node_insert_op(position: int, spec: ParagraphSpec) -> ReconstructedOp:
    op = {
        "kind": "node.insert",
        "node_kind": "paragraph",
        "position": position,
        "value": {"text": spec.text, "style": spec.style or "Normal"},
    }
    return ReconstructedOp(op=op, node_id=None)


def _node_delete_op(spec: ParagraphSpec) -> ReconstructedOp:
    op = {
        "kind": "node.delete",
        "node_id": spec.node_id or "",
        "value": {"text": spec.text, "style": spec.style or "Normal"},
    }
    return ReconstructedOp(op=op, node_id=spec.node_id)


def diff_paragraphs(
    baseline: list[ParagraphSpec], current: list[ParagraphSpec]
) -> ParagraphDiff:
    """Diff two paragraph sequences into a best-effort op stream.

    Alignment is by paragraph *text* (so a moved-but-identical paragraph stays
    aligned); aligned pairs that differ in text emit one coarse text op, and
    aligned pairs that differ in style emit a ``style.change``. Unaligned
    baseline paragraphs become ``node.delete``; unaligned current paragraphs
    become ``node.insert`` at their current position.
    """
    result = ParagraphDiff()
    base_text = [p.text for p in baseline]
    cur_text = [p.text for p in current]
    matcher = SequenceMatcher(a=base_text, b=cur_text, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for off in range(i2 - i1):
                bspec = baseline[i1 + off]
                cspec = current[j1 + off]
                style_op = _style_op(bspec, cspec)
                if style_op is not None:
                    result.ops.append(style_op)
                    result.style_changed += 1
                # Equal-by-text means no text op; style may still have moved.
        elif tag == "replace":
            # Pair the overlapping slice 1:1; surplus on either side is insert/del.
            paired = min(i2 - i1, j2 - j1)
            for off in range(paired):
                bspec = baseline[i1 + off]
                cspec = current[j1 + off]
                text_op = _intra_paragraph_op(bspec.node_id, bspec.text, cspec.text)
                if text_op is not None:
                    result.ops.append(text_op)
                    result.replaced += 1
                style_op = _style_op(bspec, cspec)
                if style_op is not None:
                    result.ops.append(style_op)
                    result.style_changed += 1
            # Extra baseline paragraphs in this block were removed.
            for off in range(paired, i2 - i1):
                result.ops.append(_node_delete_op(baseline[i1 + off]))
                result.deleted += 1
            # Extra current paragraphs in this block were added.
            for off in range(paired, j2 - j1):
                result.ops.append(_node_insert_op(j1 + off, current[j1 + off]))
                result.inserted += 1
        elif tag == "delete":
            for off in range(i2 - i1):
                result.ops.append(_node_delete_op(baseline[i1 + off]))
                result.deleted += 1
        elif tag == "insert":
            for off in range(j2 - j1):
                result.ops.append(_node_insert_op(j1 + off, current[j1 + off]))
                result.inserted += 1

    return result


def reconstruct_ops(
    baseline: list[ParagraphSpec], current: list[ParagraphSpec]
) -> list[ReconstructedOp]:
    """Convenience: return only the reconstructed op list (drops counters)."""
    return diff_paragraphs(baseline, current).ops
