"""Best-effort, paragraph-level diff reconstruction for the passive capture path.

This package exists for the *passive* "native to any model" workflow: a baseline
docx is snapshotted (``changex open``), an arbitrary model/tool/human edits the
file with no tool-calling, and then ``changex seal`` reconstructs an op stream by
diffing the current document against the stored baseline.

The reconstruction is **honest about being degraded**: it observes the *result*
of edits, never the agent / turn / prompt that caused them. The ops it produces
carry ``provenance_source='observed'`` with all declared fields ``null`` and a
``rationale`` of ``'reconstructed by passive diff'`` — see
:mod:`changex_core.passive` for how they are appended.
"""

from __future__ import annotations

from changex_core.diff.text_diff import (
    ParagraphDiff,
    ReconstructedOp,
    diff_paragraphs,
    reconstruct_ops,
)

__all__ = [
    "ParagraphDiff",
    "ReconstructedOp",
    "diff_paragraphs",
    "reconstruct_ops",
]
