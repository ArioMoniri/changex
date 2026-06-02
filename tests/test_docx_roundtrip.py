"""Round-trip check: ChangeX's native ``w:ins`` / ``w:del`` revisions resolve correctly.

This is the *serialized-bytes* counterpart to the in-process projection covered by
``test_docx_adapter.py``. That test compares the adapter's in-memory model (current
vs baseline); this one re-reads the **saved .docx** and resolves the revision markup
the way an Office engine does on Accept-All / Reject-All:

* **accept-all** == the adapter's active-capture target text, and
* **reject-all** == the baseline text.

Crucially the resolver below is the *read* path and is independent of the renderer's
model projection, so it catches serialization bugs — e.g. a deletion written with
``w:t`` instead of ``w:delText`` would make reject-all != baseline and fail here.

Note on third-party engines: an external engine (LibreOffice/Word) is the strongest
possible oracle, but headless tracked-change resolution is not reliably scriptable on
macOS (the CLI ``macro:///`` form no-ops and the bundled UNO Python is killed by
platform security), so the portable resolver here is the gating check that runs
everywhere. A real-engine oracle can be layered on in Linux CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import changex_core as cx
from changex_core.adapters.docx_adapter import DocxAdapter

pytest.importorskip("docx", reason="python-docx is required for the docx round-trip")
from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixture: a tracked .docx with REAL w:ins / w:del revisions
# --------------------------------------------------------------------------- #
def _build_tracked_docx(tmp_path: Path) -> tuple[Path, str, str]:
    """Build a tracked ``.docx`` and return ``(path, active_text, baseline_text)``.

    The two expected texts come from the adapter itself: the active-capture target
    is the current model text (what accept-all should yield) and the baseline is the
    model text before any ops (what reject-all should yield).
    """
    base = tmp_path / "base.docx"
    doc = Document()
    p = doc.add_paragraph(
        "The quick brown fox jumps over the lazy dog every single morning."
    )
    p._p.set(qn("w14:paraId"), "20000001")
    doc.add_paragraph("Prepared by the analytics team.")
    doc.save(str(base))

    adapter = DocxAdapter.load(str(base))
    model = adapter.to_model()
    baseline_text = "\n".join(par.text() for par in model.child_paragraphs())

    body = next(par for par in model.child_paragraphs() if "quick brown fox" in par.text())
    adapter.apply(cx.TextReplace(node_id=body.node_id, before="quick", after="swift"))
    adapter.apply(cx.TextDelete(node_id=body.node_id, before=" every single morning"))

    active_text = "\n".join(par.text() for par in adapter.to_model().child_paragraphs())

    tracked = tmp_path / "tracked.docx"
    adapter.save(str(tracked))

    # Sanity: the saved file really carries native revisions (else the round-trip
    # would be meaningless — nothing to accept/reject).
    xml = Document(str(tracked)).element.xml
    assert "<w:ins" in xml and "<w:del" in xml, "tracked docx lacks w:ins/w:del"
    return tracked, active_text, baseline_text


# --------------------------------------------------------------------------- #
# Portable OOXML revision resolver (read path; no external tools)
# --------------------------------------------------------------------------- #
def _within(el, tag: str) -> bool:
    """True if ``el`` has an ancestor whose (Clark-notation) tag is ``tag``."""
    parent = el.getparent()
    while parent is not None:
        if parent.tag == tag:
            return True
        parent = parent.getparent()
    return False


def _resolved_text(tracked: Path, *, accept: bool) -> str:
    """Resolve tracked revisions in a saved ``.docx`` and return paragraph text.

    Reads (does not mutate) the serialized markup and applies Office accept/reject
    semantics directly to the text-bearing nodes:

    * ``w:t`` inside ``w:ins``        -> kept only on accept-all (the insertion);
    * ``w:delText`` inside ``w:del``  -> kept only on reject-all (restored deletion);
    * any other ``w:t``               -> always kept.
    """
    doc = Document(str(tracked))
    w_t, w_del_text, w_ins, w_del = qn("w:t"), qn("w:delText"), qn("w:ins"), qn("w:del")
    lines: list[str] = []
    for para in doc.paragraphs:
        buf: list[str] = []
        for el in para._p.iter():
            if el.tag == w_t:
                if _within(el, w_ins):
                    if accept:
                        buf.append(el.text or "")
                elif not _within(el, w_del):
                    buf.append(el.text or "")
            elif el.tag == w_del_text:
                if not accept:
                    buf.append(el.text or "")
        lines.append("".join(buf))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# The gating round-trip tests (run everywhere)
# --------------------------------------------------------------------------- #
def test_accept_all_equals_active_capture(tmp_path: Path) -> None:
    """Resolving accept-all on the saved revisions == the adapter's active target."""
    tracked, active_text, _baseline = _build_tracked_docx(tmp_path)
    assert _resolved_text(tracked, accept=True) == active_text


def test_reject_all_equals_baseline(tmp_path: Path) -> None:
    """Resolving reject-all on the saved revisions == the baseline text."""
    tracked, _active, baseline_text = _build_tracked_docx(tmp_path)
    assert _resolved_text(tracked, accept=False) == baseline_text
