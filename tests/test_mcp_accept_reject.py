"""ACCEPT/REJECT MCP tool tests, driven through the transport-independent fns.

These exercise the plain :mod:`changex_mcp.tools` functions against a fresh
:class:`SessionStore` (no FastMCP/stdio transport), mirroring how the core review
loop is wired in ``tools.edit`` / ``tools.save_tracked``. The product guarantee
under test:

* ``reject(handle, op_id)`` reverts the op (``Journal.revert``) so its native
  Word revision is **genuinely absent** from the saved ``.docx`` — not merely
  flagged in the journal — and the hash chain still verifies.
* ``accept(handle, op_id)`` un-reverts it (``Journal.unrevert``) so the revision
  is restored on the next save, and the chain still verifies.
* The reject/accept markers are non-destructive: ``get_changes`` reflects the
  active set and the journal verifies throughout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

docx = pytest.importorskip("docx", reason="python-docx required for accept/reject tests")
from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

from changex_mcp import tools  # noqa: E402
from changex_mcp.session import SessionStore  # noqa: E402

# The body paragraph minted by scripts/make_sample_docx.py (paraId 10000002).
BODY_NODE_ID = "p:10000002"


def _saved_text(path: Path) -> str:
    """Join every w:t / w:delText fragment in the saved docx into one string."""
    document = Document(str(path))
    parts: list[str] = []
    for para in document.paragraphs:
        for el in para._p.iter():
            if el.tag in (qn("w:t"), qn("w:delText")) and el.text:
                parts.append(el.text)
    return " ".join(parts)


def _open_with_two_edits(store: SessionStore, src: Path):  # type: ignore[no-untyped-def]
    """Open ``src`` and make two replace_text edits; return (handle, op1, op2)."""
    opened = tools.open_tracked(
        store,
        path=str(src),
        agent_context={"model": "claude-opus-4-8", "vendor": "anthropic"},
    )
    handle = opened["handle"]
    op1 = tools.edit(
        store, handle=handle, op="replace_text",
        node_id=BODY_NODE_ID, before="quick", after="swift",
    )
    op2 = tools.edit(
        store, handle=handle, op="replace_text",
        node_id=BODY_NODE_ID, before="lazy", after="sleepy",
    )
    return handle, op1["op_id"], op2["op_id"]


def test_reject_drops_revision_from_saved_docx(tmp_path: Path, sample_docx: Path) -> None:
    store = SessionStore()
    handle, _op1, op2 = _open_with_two_edits(store, sample_docx)

    rejected = tools.reject(store, handle=handle, op_id=op2)
    assert rejected["status"] == "rejected"
    assert rejected["reverted"] is True
    assert rejected["active_ops"] == 1
    assert rejected["verified"] is True

    out = tmp_path / "out.docx"
    result = tools.save_tracked(store, handle=handle, out=str(out))
    assert result["ops"] == 1  # only the active op was rendered
    assert result["verified"] is True

    text = _saved_text(out)
    # The accepted edit is present; the rejected edit's revision is gone and the
    # original word it replaced ("lazy") is restored as plain text.
    assert "swift" in text
    assert "sleepy" not in text
    assert "lazy" in text


def test_accept_restores_a_rejected_revision(tmp_path: Path, sample_docx: Path) -> None:
    store = SessionStore()
    handle, _op1, op2 = _open_with_two_edits(store, sample_docx)

    tools.reject(store, handle=handle, op_id=op2)
    accepted = tools.accept(store, handle=handle, op_id=op2)
    assert accepted["status"] == "accepted"
    assert accepted["reverted"] is False
    assert accepted["active_ops"] == 2
    assert accepted["verified"] is True

    out = tmp_path / "restored.docx"
    result = tools.save_tracked(store, handle=handle, out=str(out))
    assert result["ops"] == 2
    assert result["verified"] is True

    text = _saved_text(out)
    # Both edits' revisions are present again after accept.
    assert "swift" in text
    assert "sleepy" in text


def test_reject_then_accept_keeps_journal_verifying(sample_docx: Path) -> None:
    store = SessionStore()
    handle, _op1, op2 = _open_with_two_edits(store, sample_docx)

    # get_changes reflects the active set and the chain verifies at each step.
    before = tools.get_changes(store, handle=handle)
    assert before["count"] == 2
    assert before["verified"] is True

    tools.reject(store, handle=handle, op_id=op2)
    during = tools.get_changes(store, handle=handle)
    assert during["count"] == 1  # rejected op leaves the active set
    assert during["verified"] is True

    tools.accept(store, handle=handle, op_id=op2)
    after = tools.get_changes(store, handle=handle)
    assert after["count"] == 2  # accept brings it back
    assert after["verified"] is True


def test_reject_unknown_op_id_is_structured_error(sample_docx: Path) -> None:
    store = SessionStore()
    handle, _op1, _op2 = _open_with_two_edits(store, sample_docx)
    with pytest.raises(tools.ToolError) as exc:
        tools.reject(store, handle=handle, op_id="does-not-exist")
    assert exc.value.code == "unknown_op_id"


def test_accept_unknown_op_id_is_structured_error(sample_docx: Path) -> None:
    store = SessionStore()
    handle, _op1, _op2 = _open_with_two_edits(store, sample_docx)
    with pytest.raises(tools.ToolError) as exc:
        tools.accept(store, handle=handle, op_id="does-not-exist")
    assert exc.value.code == "unknown_op_id"


def test_accept_op_never_rejected_is_noop(sample_docx: Path) -> None:
    store = SessionStore()
    handle, _op1, op2 = _open_with_two_edits(store, sample_docx)
    # Accepting an op that was never rejected leaves it active and verifying.
    result = tools.accept(store, handle=handle, op_id=op2)
    assert result["reverted"] is False
    assert result["active_ops"] == 2
    assert result["verified"] is True
