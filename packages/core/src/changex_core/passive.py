"""Passive "native to any model" capture: ``changex open`` / ``changex seal``.

This is the offline / no-tool-calling path. Any model — a local LLM with no
function calling, a CLI tool, or a human in Word — can participate:

* ``open``  snapshots the baseline docx (:func:`changex_core.baseline.snapshot`)
  and writes a ``.changex`` header with ``capture_mode='passive'``. No ops yet.
* ``seal``  diffs the *current* docx against the stored baseline, reconstructs a
  best-effort paragraph-level op stream (:mod:`changex_core.diff`), and appends
  each op with **degraded** provenance: ``agent`` / ``vendor`` / ``turn_id`` /
  ``prompt_sha256`` are ``null``, ``provenance_source='observed'`` and
  ``rationale='reconstructed by passive diff'``.

Honesty is the contract here. Passive ops are *observations of the net textual
delta*, not true provenance — the journal must never present a reconstructed op
as if a known model declared it. Callers and the CLI surface that explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from changex_core.adapters.docx_adapter import DocxAdapter
from changex_core.baseline import Baseline, snapshot
from changex_core.diff.text_diff import ParagraphSpec, diff_paragraphs
from changex_core.journal.events import Header, Provenance, Target, utc_now_iso
from changex_core.journal.journal import Journal
from changex_core.model.nodes import NodeKind
from changex_core.ops.vocabulary import op_from_dict
from changex_core.paths import safe_path
from changex_core.render.save import save_active

CAPTURE_MODE = "passive"
PASSIVE_RATIONALE = "reconstructed by passive diff"
PASSIVE_PROVENANCE_SOURCE = "observed"


def _default_changex_path(docx_path: Path) -> Path:
    """Return the sidecar ``.changex`` path next to ``docx_path``."""
    return docx_path.with_suffix(".changex")


def _baseline_sidecar_path(changex_path: Path) -> Path:
    """Return the preserved-baseline sidecar path for a journal.

    Passive capture frequently edits the *same* docx in place (that's the whole
    point — any tool just opens and saves it), so the original baseline bytes
    must be preserved out-of-band or there is nothing to diff against at seal
    time. We snapshot them next to the journal as ``<stem>.baseline.docx``.
    """
    return changex_path.with_suffix(".baseline.docx")


def _paragraph_specs(docx_path: Path) -> list[ParagraphSpec]:
    """Extract ``(node_id, text, style)`` per paragraph via the docx adapter.

    Reusing :class:`DocxAdapter` means baseline node_ids are derived from Word's
    native ``w14:paraId`` (stable across the open/edit/seal round-trip) exactly
    as the active path derives them.
    """
    adapter = DocxAdapter.load(str(docx_path))
    model = adapter.to_model()
    specs: list[ParagraphSpec] = []
    for node in model.children:
        if node.node_kind != NodeKind.PARAGRAPH:
            continue
        specs.append(
            ParagraphSpec(
                node_id=node.node_id,
                text=node.text(),
                style=str(node.attrs.get("style", "Normal")),
            )
        )
    return specs


def _passive_provenance(session_id: str) -> Provenance:
    """Build the honest, degraded provenance attached to reconstructed ops."""
    return Provenance(
        ts=utc_now_iso(),
        session_id=session_id,
        tool_call_id=None,
        client_name=None,
        client_version=None,
        agent=None,
        vendor=None,
        turn_id=None,
        prompt_sha256=None,
        rationale=PASSIVE_RATIONALE,
        provenance_source=PASSIVE_PROVENANCE_SOURCE,
    )


@dataclass
class OpenResult:
    """Outcome of :func:`open_passive`."""

    changex_path: Path
    baseline: Baseline
    session_id: str
    paragraphs: int


@dataclass
class SealResult:
    """Outcome of :func:`seal_passive`."""

    changex_path: Path
    appended: int
    replaced: int
    inserted: int
    deleted: int
    style_changed: int
    baseline_unchanged: bool
    degraded: bool = True
    tracked_path: Optional[Path] = None


def open_passive(docx: str, changex: Optional[str] = None) -> OpenResult:
    """Snapshot ``docx`` and write a pending passive journal header.

    The header records ``capture_mode='passive'`` and the baseline sha256 + uri so
    a later :func:`seal_passive` can diff against the exact opened bytes. No ops
    are written — any tool may now edit the docx freely.
    """
    doc_path = safe_path(docx, must_exist=True, allow_suffixes=(".docx",))
    changex_path = (
        safe_path(changex, allow_suffixes=(".changex", ".jsonl"))
        if changex
        else _default_changex_path(doc_path)
    )

    baseline = snapshot(str(doc_path))
    specs = _paragraph_specs(doc_path)

    # Preserve the exact opened bytes so seal can diff even if the user edits the
    # original docx in place. The sidecar lives beside the journal.
    changex_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar = _baseline_sidecar_path(changex_path)
    sidecar.write_bytes(doc_path.read_bytes())

    header = Header.create(
        baseline_sha256=baseline.sha256,
        filename=doc_path.name,
        baseline_uri=str(sidecar),
        capture_mode=CAPTURE_MODE,
        node_id_map={s.node_id: s.node_id for s in specs if s.node_id},
    )
    journal = Journal.open(str(changex_path), header=header)
    return OpenResult(
        changex_path=changex_path,
        baseline=baseline,
        session_id=journal.header.session_id,
        paragraphs=len(specs),
    )


def seal_passive(docx: str, changex: Optional[str] = None) -> SealResult:
    """Diff the current ``docx`` vs the stored baseline and append passive ops.

    Reconstructs a coarse, paragraph-level op stream and appends each op with
    degraded provenance. Returns a :class:`SealResult` with per-kind counts and a
    ``degraded=True`` flag so callers can be honest about what was captured.

    Raises:
        ValueError: if the journal is not a passive-capture journal, or its
            ``baseline_uri`` is missing/unreadable (we cannot diff without it).
    """
    doc_path = safe_path(docx, must_exist=True, allow_suffixes=(".docx",))
    changex_path = (
        safe_path(changex, must_exist=True, allow_suffixes=(".changex", ".jsonl"))
        if changex
        else safe_path(str(_default_changex_path(doc_path)), must_exist=True)
    )

    journal = Journal.open(str(changex_path))
    header = journal.header
    if header.session.get("capture_mode") != CAPTURE_MODE:
        raise ValueError(
            f"journal {changex_path} is not a passive-capture journal "
            "(run `changex open` first to start a passive session)"
        )

    baseline_uri = header.doc.get("baseline_uri")
    if not baseline_uri:
        raise ValueError(
            "passive seal requires a stored baseline_uri in the header; "
            "the original baseline document was not recorded at open time"
        )
    baseline_path = safe_path(str(baseline_uri), must_exist=True, allow_suffixes=(".docx",))

    baseline_specs = _paragraph_specs(baseline_path)
    current_specs = _paragraph_specs(doc_path)

    diff = diff_paragraphs(baseline_specs, current_specs)
    session_id = header.session_id

    for rec in diff.ops:
        op = op_from_dict(rec.op)
        target = Target(
            node_id=rec.node_id or "",
            node_kind=rec.node_kind,
            path="",
        )
        journal.append(op, target, _passive_provenance(session_id))

    baseline_unchanged = not diff.ops

    # Best-effort: also render a Word-openable tracked .docx by replaying the
    # reconstructed ops onto the baseline, so the passive path has something for
    # `changex review --doc` / `changex view --doc` / Word. Reconstructed ops can be
    # coarse (whole-paragraph), which may trip the active adapter's size guard — if
    # so we still return the journal, just without a tracked file.
    tracked_path: Optional[Path] = None
    if diff.ops:
        candidate = changex_path.with_name(changex_path.stem + ".tracked.docx")
        try:
            save_active(journal, str(baseline_path), str(candidate), author="passive (reconstructed)")
            tracked_path = candidate
        except Exception:
            tracked_path = None

    return SealResult(
        changex_path=changex_path,
        appended=diff.total,
        replaced=diff.replaced,
        inserted=diff.inserted,
        deleted=diff.deleted,
        style_changed=diff.style_changed,
        baseline_unchanged=baseline_unchanged,
        degraded=True,
        tracked_path=tracked_path,
    )
