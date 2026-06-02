"""DocxAdapter op tests against a real generated ``.docx``.

These cover the gating M0 addressing + op-application criteria via the public
``changex_core`` API:

* opaque, edit-invariant paragraph ids (native ``w14:paraId`` reuse), with
  duplicate-content paragraphs getting DISTINCT ids (no content-hash collision)
  and paraId-less paragraphs getting a minted, stable id;
* the six v0.1 ops apply and project correctly (accept-all == current text,
  reject-all == baseline text);
* two edits to the SAME paragraph + an insert above it keep every node_id stable;
* before-substring + op-size validation refuse bad ops at the boundary;
* the journal of those ops verifies and replays back to the live model, and a
  MIDDLE-op revert leaves the rest resolving.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import changex_core as cx
from changex_core.journal.events import utc_now_iso

pytest.importorskip("docx", reason="python-docx is required for the docx adapter")

from docx import Document  # noqa: E402  (after importorskip)
from docx.oxml.ns import qn  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _ids(adapter: cx.DocxAdapter) -> list[str]:
    return [p.node_id for p in adapter.to_model().child_paragraphs()]


def _text_of(adapter: cx.DocxAdapter, node_id: str) -> str:
    node = adapter.to_model().find(node_id)
    assert node is not None
    return node.text()


def _prov(session_id: str) -> cx.Provenance:
    return cx.Provenance(
        ts=utc_now_iso(),
        session_id=session_id,
        agent="claude-opus-4-8",
        vendor="anthropic",
        provenance_source="declared",
    )


# --------------------------------------------------------------------------- #
# Addressing: opaque, edit-invariant, collision-free
# --------------------------------------------------------------------------- #
def test_paragraph_ids_reuse_native_para_id(sample_docx: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx))
    ids = _ids(adapter)
    # The fixture stamps paraId 10000001..10000006; the adapter namespaces as p:<paraId>.
    assert "p:10000001" in ids  # heading
    assert "p:10000002" in ids  # body
    # node_id_map records the carrier (the paraId) for every paragraph.
    carriers = adapter.node_id_map()
    assert carriers["p:10000001"] == "10000001"


def test_duplicate_content_paragraphs_get_distinct_ids(sample_docx: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx))
    paras = adapter.to_model().child_paragraphs()
    dup = [p for p in paras if p.text() == "This line is intentionally duplicated."]
    assert len(dup) == 2
    # Identical text, DIFFERENT node_ids — proves ids are not content hashes.
    assert dup[0].node_id != dup[1].node_id


def test_para_id_less_paragraph_gets_minted_stable_id(sample_docx: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx))
    target = next(
        p for p in adapter.to_model().child_paragraphs() if "no native paraId" in p.text()
    )
    assert target.node_id  # a stable id was minted
    # The minted id is recorded in the carrier map for persistence.
    assert target.node_id in adapter.node_id_map()


def test_ids_unchanged_after_two_edits_and_insert_above(sample_docx: Path) -> None:
    """GATING: two edits to one paragraph + insert above leave ids stable."""
    adapter = cx.DocxAdapter.load(str(sample_docx))
    body_id = _ids(adapter)[1]  # the quick-brown-fox sentence
    original_ids = set(_ids(adapter))

    adapter.apply(cx.TextReplace(node_id=body_id, before="quick", after="swift"))
    adapter.apply(cx.TextReplace(node_id=body_id, before="lazy", after="sleepy"))
    adapter.apply(
        cx.NodeInsert(
            node_kind="paragraph", position=1, value={"text": "Inserted above.", "style": "Normal"}
        )
    )

    after_ids = set(_ids(adapter))
    # Every original id still resolves (the body id survived two edits + an insert).
    assert original_ids.issubset(after_ids)
    assert adapter.to_model().find(body_id) is not None
    assert _text_of(adapter, body_id) == (
        "The swift brown fox jumps over the sleepy dog every single morning."
    )


# --------------------------------------------------------------------------- #
# v0.1 op application + accept/reject projection
# --------------------------------------------------------------------------- #
def test_text_replace_projects_accept_and_reject(sample_docx: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx))
    body_id = _ids(adapter)[1]
    baseline_text = _text_of(adapter, body_id)
    adapter.apply(cx.TextReplace(node_id=body_id, before="quick", after="swift"))
    # current (accept-all) text contains the replacement; baseline restores it.
    assert "swift" in _text_of(adapter, body_id)
    assert "quick" not in _text_of(adapter, body_id)
    para = next(p for p in adapter._paras if p.node_id == body_id)  # internal projection check
    assert para.current_text() == _text_of(adapter, body_id)
    assert para.baseline_text() == baseline_text


def test_text_delete_removes_from_current_keeps_in_baseline(sample_docx: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx))
    body_id = _ids(adapter)[1]
    adapter.apply(cx.TextDelete(node_id=body_id, before=" every single morning"))
    para = next(p for p in adapter._paras if p.node_id == body_id)
    assert "every single morning" not in para.current_text()  # accept-all drops it
    assert "every single morning" in para.baseline_text()  # reject-all keeps it


def test_text_insert_after_anchor_and_at_end(sample_docx: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx))
    body_id = _ids(adapter)[1]
    adapter.apply(cx.TextInsert(node_id=body_id, before_anchor="fox", text=" (red)"))
    assert "fox (red)" in _text_of(adapter, body_id)
    adapter.apply(cx.TextInsert(node_id=body_id, before_anchor=None, text=" THE END"))
    assert _text_of(adapter, body_id).endswith(" THE END")


def test_style_change_updates_style_and_validates_before(sample_docx: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx))
    heading_id = _ids(adapter)[0]
    adapter.apply(cx.StyleChange(node_id=heading_id, style="Heading 2", before="Heading 1"))
    heading = adapter.to_model().find(heading_id)
    assert heading.attrs["style"] == "Heading 2"
    # A wrong `before` style must be refused.
    with pytest.raises(cx.BeforeMismatchError):
        adapter.apply(cx.StyleChange(node_id=heading_id, style="Title", before="Heading 1"))


def test_node_insert_and_node_delete(sample_docx: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx))
    before_count = len(adapter.to_model().child_paragraphs())
    adapter.apply(
        cx.NodeInsert(
            node_kind="paragraph", position=0, value={"text": "Brand new top line.", "style": "Normal"}
        )
    )
    paras = adapter.to_model().child_paragraphs()
    assert len(paras) == before_count + 1
    assert paras[0].text() == "Brand new top line."

    delete_id = paras[-1].node_id
    adapter.apply(cx.NodeDelete(node_id=delete_id, value={"text": paras[-1].text()}))
    # node.delete removes the paragraph from the current (accept-all) model.
    assert adapter.to_model().find(delete_id) is None


# --------------------------------------------------------------------------- #
# Boundary guards: before-mismatch + oversized op
# --------------------------------------------------------------------------- #
def test_before_mismatch_is_refused(sample_docx: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx))
    body_id = _ids(adapter)[1]
    with pytest.raises(cx.BeforeMismatchError):
        adapter.apply(cx.TextReplace(node_id=body_id, before="not-present", after="x"))
    with pytest.raises(cx.BeforeMismatchError):
        adapter.apply(cx.TextDelete(node_id=body_id, before=""))  # empty before


def test_oversized_op_is_refused_with_split_required(sample_docx: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx))
    body_id = _ids(adapter)[1]
    whole = _text_of(adapter, body_id)  # rewriting the entire node > 50%
    with pytest.raises(cx.OversizedOpError) as exc:
        adapter.apply(cx.TextReplace(node_id=body_id, before=whole, after="short"))
    assert "split_required" in str(exc.value)


def test_unknown_node_id_is_refused(sample_docx: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx))
    with pytest.raises(cx.NodeNotFoundError):
        adapter.apply(cx.TextReplace(node_id="p:DOESNOTEXIST", before="a", after="b"))


# --------------------------------------------------------------------------- #
# Tracked save: native deletions use w:delText, not w:t; w:id unique
# --------------------------------------------------------------------------- #
def test_render_tracked_uses_deltext_and_unique_wids(sample_docx: Path, tmp_path: Path) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx), author="claude-opus-4-8")
    body_id = _ids(adapter)[0 + 1]
    adapter.apply(cx.TextReplace(node_id=body_id, before="quick", after="swift"))
    adapter.apply(cx.TextDelete(node_id=body_id, before=" every single morning"))
    out = tmp_path / "tracked.docx"
    adapter.save(str(out))

    doc = Document(str(out))
    body = doc.element.body
    # Deletions must use w:delText (never w:t) inside w:del.
    dels = body.findall(".//" + qn("w:del"))
    assert dels, "expected at least one w:del element"
    for d in dels:
        assert d.findall(".//" + qn("w:delText"))  # delText present
        assert not d.findall(".//" + qn("w:t"))  # no plain w:t inside a deletion

    # Every revision w:id must be unique across w:ins / w:del.
    wids = [
        el.get(qn("w:id"))
        for tag in ("w:ins", "w:del")
        for el in body.findall(".//" + qn(tag))
    ]
    assert wids, "expected revision elements with w:id"
    assert len(wids) == len(set(wids)), "revision w:id values must be unique"

    # The model author is recorded on the revisions.
    authors = {el.get(qn("w:author")) for el in body.findall(".//" + qn("w:ins"))}
    assert "claude-opus-4-8" in authors


# --------------------------------------------------------------------------- #
# Journal integration over the docx adapter: verify + replay + middle revert
# --------------------------------------------------------------------------- #
def test_journal_over_docx_verifies_replays_and_reverts(
    sample_docx: Path, journal_path: Path
) -> None:
    adapter = cx.DocxAdapter.load(str(sample_docx), author="claude-opus-4-8")
    baseline = cx.Node.from_dict(adapter.to_model().to_dict())
    body_id = _ids(adapter)[1]
    heading_id = _ids(adapter)[0]

    header = cx.Header.create(
        baseline_sha256=adapter.baseline_sha256(),
        filename=sample_docx.name,
        node_id_map=adapter.node_id_map(),
    )
    journal = cx.Journal.open(str(journal_path), header=header)
    sid = journal.header.session_id

    def record(op: cx.Op, node_id: str) -> cx.Event:
        adapter.apply(op)
        return journal.append(op, cx.Target(node_id=node_id, node_kind="paragraph"), _prov(sid))

    e1 = record(cx.TextReplace(node_id=body_id, before="quick", after="swift"), body_id)
    e2 = record(cx.TextReplace(node_id=body_id, before="lazy", after="sleepy"), body_id)
    record(cx.StyleChange(node_id=heading_id, style="Heading 2", before="Heading 1"), heading_id)
    record(
        cx.NodeInsert(
            node_kind="paragraph", position=1, value={"text": "Summary.", "style": "Normal"}
        ),
        "(inserted)",
    )
    record(cx.TextInsert(node_id=body_id, before_anchor="morning", text=" sharp"), body_id)

    # Hash chain verifies and replay reproduces the live model.
    assert journal.verify().ok
    fresh = cx.DocxAdapter.load(str(sample_docx), author="claude-opus-4-8")
    replayed = journal.replay(fresh, baseline)
    live = {p.node_id: p.text() for p in adapter.to_model().child_paragraphs()}
    assert {p.node_id: p.text() for p in replayed.child_paragraphs()} == live

    # Reject a MIDDLE op (lazy -> sleepy): 'swift' kept, 'lazy' restored.
    journal.revert(e2.op_id)
    assert not journal.is_reverted(e1.op_id)
    fresh2 = cx.DocxAdapter.load(str(sample_docx), author="claude-opus-4-8")
    after_revert = journal.replay(fresh2, baseline)
    body_after = after_revert.find(body_id).text()
    assert "swift" in body_after  # e1 still applied
    assert "lazy" in body_after  # e2 reverted
    assert "sleepy" not in body_after
