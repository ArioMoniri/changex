"""CsvAdapter op tests against a real generated ``.csv`` (M3).

These cover, via the public ``changex_core`` API + the registry:

* natural-key cell addressing (``"<stem>!<ref>"``) with a stored ``row_id`` so a
  cell follows its row under ``row.insert``;
* ``cell.set`` / ``row.insert`` / ``row.delete`` apply and project; ``formula.set``
  is rejected (no formula evaluation in csv);
* ``before``-mismatch + out-of-range guards refuse bad ops at the boundary;
* ``render_tracked`` returns a unified + side-by-side HTML redline (the ONLY
  review surface — csv has no native revisions) and the clean csv is shippable;
* the journal of those ops verifies and replays back to the live model.

csv has NO native track-changes: the journal + HTML redline ARE the review
surface, and this is stated in the adapter docstring.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import changex_core as cx
from changex_core.adapters import load_adapter
from changex_core.adapters.csv_adapter import CsvAdapter


# --------------------------------------------------------------------------- #
# fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    """A small 3-row csv: a header plus two data rows."""
    out = tmp_path / "data.csv"
    out.write_text("name,score\nalice,10\nbob,20\n", encoding="utf-8")
    return out


def _prov(session_id: str) -> cx.Provenance:
    return cx.Provenance(
        ts="2026-06-02T00:00:00Z",
        session_id=session_id,
        agent="claude-opus-4-8",
        vendor="anthropic",
        provenance_source="declared",
    )


# --------------------------------------------------------------------------- #
# Addressing: natural key + row-following rowId
# --------------------------------------------------------------------------- #
def test_cells_addressed_by_natural_key(sample_csv: Path) -> None:
    adapter = load_adapter(str(sample_csv))
    assert isinstance(adapter, CsvAdapter)
    model = adapter.to_model()
    a2 = model.find("data!A2")
    assert a2 is not None and a2.value == "alice"
    b3 = model.find("data!B3")
    assert b3 is not None and b3.value == "20"


def test_cell_follows_its_row_under_row_insert(sample_csv: Path) -> None:
    adapter = load_adapter(str(sample_csv))
    alice_before = adapter.to_model().find("data!A2")
    original_row_id = alice_before.attrs["row_id"]

    adapter.apply(cx.RowInsert(sheet="data", at=2))  # insert above alice

    after = adapter.to_model()
    moved = after.find("data!A3")
    assert moved is not None and moved.value == "alice"
    assert moved.attrs["row_id"] == original_row_id


# --------------------------------------------------------------------------- #
# v0.2 op application
# --------------------------------------------------------------------------- #
def test_cell_set_updates_value_and_validates_before(sample_csv: Path) -> None:
    adapter = load_adapter(str(sample_csv))
    adapter.apply(cx.CellSet(sheet="data", ref="B2", before="10", after="15"))
    assert adapter.to_model().find("data!B2").value == "15"
    with pytest.raises(cx.BeforeMismatchError):
        adapter.apply(cx.CellSet(sheet="data", ref="B2", before="10", after="99"))


def test_row_insert_and_row_delete(sample_csv: Path) -> None:
    adapter = load_adapter(str(sample_csv))
    adapter.apply(cx.RowDelete(sheet="data", at=3, value=["bob", "20"]))
    # bob's row is gone from the model.
    model = adapter.to_model()
    assert all(n.value != "bob" for n in model.children)


def test_row_delete_out_of_range_is_refused(sample_csv: Path) -> None:
    adapter = load_adapter(str(sample_csv))
    with pytest.raises(cx.NodeNotFoundError):
        adapter.apply(cx.RowDelete(sheet="data", at=99, value=[]))


def test_formula_set_is_rejected_for_csv(sample_csv: Path) -> None:
    adapter = load_adapter(str(sample_csv))
    with pytest.raises(TypeError):
        adapter.apply(cx.FormulaSet(sheet="data", ref="A1", before="name", after="=1"))


# --------------------------------------------------------------------------- #
# Overlay: HTML redline is the (only) review surface; clean csv is shippable
# --------------------------------------------------------------------------- #
def test_render_tracked_is_unified_and_side_by_side_redline(sample_csv: Path) -> None:
    adapter = load_adapter(str(sample_csv))
    adapter.apply(cx.CellSet(sheet="data", ref="B2", before="10", after="15"))
    adapter.apply(cx.RowInsert(sheet="data", at=2))
    adapter.apply(cx.RowDelete(sheet="data", at=4, value=["bob", "20"]))

    html = adapter.render_tracked().decode("utf-8")
    assert "Unified redline" in html and "Side-by-side" in html
    # the edited cell shows before crossed out + after inserted
    assert "<del>10</del>" in html and "<ins>15</ins>" in html
    # the honesty note is present (no native track-changes)
    assert "no native track-changes" in html


def test_clean_csv_is_plain_shippable_output(sample_csv: Path) -> None:
    adapter = load_adapter(str(sample_csv))
    adapter.apply(cx.CellSet(sheet="data", ref="B2", before="10", after="15"))
    adapter.apply(cx.RowDelete(sheet="data", at=3, value=["bob", "20"]))

    clean = adapter.clean_csv_bytes().decode("utf-8")
    assert "15" in clean and "bob" not in clean
    assert "<del>" not in clean and "<ins>" not in clean  # no redline markup in the csv


def test_save_writes_clean_csv_and_sibling_review_html(sample_csv: Path, tmp_path: Path) -> None:
    adapter = load_adapter(str(sample_csv))
    adapter.apply(cx.CellSet(sheet="data", ref="B2", before="10", after="15"))
    out = tmp_path / "out.csv"
    adapter.save(str(out))
    review = out.with_suffix(".review.html")
    assert out.exists() and review.exists()
    assert "15" in out.read_text(encoding="utf-8")
    assert "Unified redline" in review.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Journal integration: verify + replay back to the live model
# --------------------------------------------------------------------------- #
def test_journal_over_csv_verifies_and_replays(sample_csv: Path, tmp_path: Path) -> None:
    adapter = load_adapter(str(sample_csv), author="m")
    baseline = cx.Node.from_dict(adapter.to_model().to_dict())

    header = cx.Header.create(
        baseline_sha256=adapter.baseline_sha256(),
        filename=sample_csv.name,
        doc_format="csv",
    )
    journal = cx.Journal.open(str(tmp_path / "s.changex"), header=header)
    sid = journal.header.session_id

    def record(op: cx.Op) -> cx.Event:
        adapter.apply(op)
        node_id = cx.target_node_id(op) or ""
        node = adapter.resolve(node_id)
        target = cx.Target(
            node_id=node_id,
            node_kind=node.node_kind.value if node else "paragraph",
            path=node.path if node else "",
        )
        return journal.append(op, target, _prov(sid))

    record(cx.CellSet(sheet="data", ref="B2", before="10", after="15"))
    record(cx.RowInsert(sheet="data", at=2))

    assert journal.verify().ok
    fresh = load_adapter(str(sample_csv), author="m")
    replayed = journal.replay(fresh, baseline)
    live = {n.node_id: n.value for n in adapter.to_model().children}
    assert {n.node_id: n.value for n in replayed.children} == live
