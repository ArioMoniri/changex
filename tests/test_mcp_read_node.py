"""``read_node`` returns a paragraph's FULL current text.

The regression it guards: ``get_outline`` only returns a ~120-char *preview* of each
paragraph. Without a way to read the rest, an editing agent cannot supply an exact
``before`` for wording in the middle or end of a long paragraph — and the ``edit`` guard
(correctly) refuses a ``before`` it can't match, so that text becomes un-editable. The
text ``read_node`` returns is the *same* current text the guard matches ``before``
against, so any substring of it is a valid ``before`` (no blind edits).
"""

from __future__ import annotations

from pathlib import Path

import pytest

docx = pytest.importorskip("docx", reason="python-docx required for read_node tests")
from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

from changex_mcp import tools  # noqa: E402
from changex_mcp.outline import PREVIEW_CHARS  # noqa: E402
from changex_mcp.session import SessionStore  # noqa: E402

NODE_ID = "p:20000001"
# A paragraph deliberately longer than the outline preview, with a distinctive clinical
# detail ("hyponatraemia") well PAST the truncation point — invisible in the preview.
LONG = (
    "The patient was a 54-year-old previously healthy man who presented to the "
    "emergency department with a three-week history of progressive fatigue and nausea, "
    "and laboratory testing on admission confirmed severe hyponatraemia requiring "
    "careful, monitored correction."
)


def _doc(tmp_path: Path) -> Path:
    base = tmp_path / "case.docx"
    document = Document()
    para = document.add_paragraph(LONG)
    para._p.set(qn("w14:paraId"), "20000001")
    document.save(str(base))
    return base


def _open(store: SessionStore, src: Path) -> str:
    return tools.open_tracked(
        store,
        path=str(src),
        agent_context={"model": "claude-opus-4-8", "vendor": "anthropic"},
    )["handle"]


def test_outline_preview_truncates_but_read_node_returns_full_text(tmp_path: Path) -> None:
    store = SessionStore()
    handle = _open(store, _doc(tmp_path))

    outline = tools.get_outline(store, handle=handle)
    entry = outline["nodes"][0]
    preview = entry["preview"]
    assert len(preview) <= PREVIEW_CHARS
    assert preview.endswith("…")  # visibly truncated
    assert "hyponatraemia" not in preview  # the key detail is past the cutoff
    # The truncation announces itself so an agent knows to read the rest.
    assert entry["truncated"] is True
    assert entry["chars"] == len(LONG)
    # The preview is cut on a WORD boundary (not mid-word like "…produce a v").
    stem = preview[:-2].rstrip()  # drop the trailing " …"
    flat = " ".join(LONG.split())
    assert flat.startswith(stem) and flat[len(stem)] == " "
    assert "read_node" in outline["note"]  # the result itself points to the fix

    node = tools.read_node(store, handle=handle, node_id=NODE_ID)
    assert node["text"] == LONG  # the WHOLE paragraph, not the preview
    assert node["length"] == len(LONG)
    assert "hyponatraemia" in node["text"]  # now visible


def test_read_node_text_is_a_valid_before_for_a_mid_paragraph_edit(tmp_path: Path) -> None:
    store = SessionStore()
    handle = _open(store, _doc(tmp_path))

    text = tools.read_node(store, handle=handle, node_id=NODE_ID)["text"]
    # A substring from PAST the preview cutoff — the part an agent could not see.
    needle = "severe hyponatraemia"
    assert text.index(needle) > PREVIEW_CHARS

    # It matches the edit guard exactly — no before_mismatch.
    result = tools.edit(
        store,
        handle=handle,
        op="replace_text",
        node_id=NODE_ID,
        before=needle,
        after="profound hyponatraemia",
    )
    assert "op_id" in result and result.get("node_id") == NODE_ID

    # read_node now reflects the updated current text (it reads live state, not baseline).
    after = tools.read_node(store, handle=handle, node_id=NODE_ID)["text"]
    assert "profound hyponatraemia" in after


def test_read_node_unknown_node_id_errors(tmp_path: Path) -> None:
    store = SessionStore()
    handle = _open(store, _doc(tmp_path))
    with pytest.raises(tools.ToolError) as excinfo:
        tools.read_node(store, handle=handle, node_id="p:does-not-exist")
    assert excinfo.value.code == "node_not_found"
