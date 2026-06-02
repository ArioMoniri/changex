"""Journal contract tests: append / read / replay / verify / revert + tamper.

These tests exercise the journal in isolation from any heavy adapter by driving
it with a tiny in-process :class:`DocumentAdapter` over a single-paragraph model.
That keeps the hash-chain / replay / revert invariants under test even where
``python-docx`` is unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import changex_core as cx
from changex_core.journal.events import utc_now_iso


# --------------------------------------------------------------------------- #
# A minimal in-memory adapter so journal tests don't depend on python-docx.
# It models a flat list of paragraphs, each a single text run.
# --------------------------------------------------------------------------- #
class FakeAdapter(cx.DocumentAdapter):
    """Tiny single-level paragraph adapter implementing the public contract."""

    def __init__(self, paragraphs: list[tuple[str, str]]) -> None:
        # paragraphs: list of (node_id, text)
        self._paras: list[list[str]] = [[nid, txt] for nid, txt in paragraphs]
        self._baseline = "0" * 64

    @classmethod
    def load(cls, path: str) -> "FakeAdapter":  # pragma: no cover - not used
        raise NotImplementedError

    def baseline_sha256(self) -> str:
        return self._baseline

    def to_model(self) -> cx.Node:
        root = cx.Node(node_id="root", node_kind=cx.NodeKind.DOCUMENT)
        for idx, (nid, txt) in enumerate(self._paras):
            root.children.append(
                cx.Node(
                    node_id=nid,
                    node_kind=cx.NodeKind.PARAGRAPH,
                    path=f"/p[{idx}]",
                    value=txt,
                )
            )
        return root

    def set_model(self, root: cx.Node) -> None:
        self._paras = [[p.node_id, str(p.value or "")] for p in root.child_paragraphs()]

    def resolve(self, node_id: str) -> cx.Node | None:
        return self.to_model().find(node_id)

    def _row(self, node_id: str) -> list[str]:
        for row in self._paras:
            if row[0] == node_id:
                return row
        raise cx.NodeNotFoundError(node_id)

    def apply(self, op: cx.Op) -> None:
        if isinstance(op, cx.TextReplace):
            row = self._row(op.node_id)
            if op.before not in row[1]:
                raise cx.BeforeMismatchError(op.before)
            row[1] = row[1].replace(op.before, op.after, 1)
        elif isinstance(op, cx.TextInsert):
            row = self._row(op.node_id)
            if op.before_anchor is None:
                row[1] = row[1] + op.text
            else:
                idx = row[1].find(op.before_anchor)
                if idx == -1:
                    raise cx.BeforeMismatchError(op.before_anchor)
                cut = idx + len(op.before_anchor)
                row[1] = row[1][:cut] + op.text + row[1][cut:]
        elif isinstance(op, cx.TextDelete):
            row = self._row(op.node_id)
            if op.before not in row[1]:
                raise cx.BeforeMismatchError(op.before)
            row[1] = row[1].replace(op.before, "", 1)
        else:  # pragma: no cover - other ops not needed by these tests
            raise TypeError(type(op).__name__)

    def render_tracked(self) -> bytes:  # pragma: no cover - not exercised
        return b""

    def save(self, out_path: str) -> None:  # pragma: no cover - not exercised
        pass


def _prov(journal: cx.Journal, **kw: object) -> cx.Provenance:
    return cx.Provenance(ts=utc_now_iso(), session_id=journal.header.session_id, **kw)


def _open_journal(path: Path, *, node_id_map: dict[str, str] | None = None) -> cx.Journal:
    header = cx.Header.create(
        baseline_sha256="0" * 64,
        filename="fake.docx",
        node_id_map=node_id_map or {},
    )
    return cx.Journal.open(str(path), header=header)


def _target(node_id: str) -> cx.Target:
    return cx.Target(node_id=node_id, node_kind="paragraph", path="")


# --------------------------------------------------------------------------- #
# Header / open lifecycle
# --------------------------------------------------------------------------- #
def test_open_writes_header_and_requires_one_for_new(journal_path: Path) -> None:
    with pytest.raises(cx.JournalError):
        cx.Journal.open(str(journal_path))  # no header on a fresh path
    journal = _open_journal(journal_path)
    assert journal_path.exists()
    first_line = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])
    assert first_line["type"] == "header"
    assert first_line["doc"]["baseline_sha256"] == "0" * 64
    assert journal.header.session_id


def test_open_reloads_existing_chain_state(journal_path: Path) -> None:
    journal = _open_journal(journal_path)
    op = cx.TextReplace(node_id="p:1", before="old", after="new")
    journal.append(op, _target("p:1"), _prov(journal))
    assert journal.last_seq == 1
    # Re-open the same file: seq + hash state must be recovered.
    reopened = cx.Journal.open(str(journal_path))
    assert reopened.last_seq == 1
    assert reopened.header.session_id == journal.header.session_id
    assert reopened.verify().ok


# --------------------------------------------------------------------------- #
# Append + read
# --------------------------------------------------------------------------- #
def test_append_assigns_monotonic_seq_and_links_hash_chain(journal_path: Path) -> None:
    journal = _open_journal(journal_path)
    e1 = journal.append(
        cx.TextReplace(node_id="p:1", before="a", after="b"), _target("p:1"), _prov(journal)
    )
    e2 = journal.append(
        cx.TextReplace(node_id="p:1", before="b", after="c"), _target("p:1"), _prov(journal)
    )
    assert (e1.seq, e2.seq) == (1, 2)
    assert e1.prev_hash is None  # genesis link
    assert e2.prev_hash == e1.hash  # chained
    assert e1.hash and e2.hash and e1.hash != e2.hash
    events = list(journal.read())
    assert [e.op_id for e in events] == [e1.op_id, e2.op_id]


def test_append_persists_provenance_split(journal_path: Path) -> None:
    journal = _open_journal(journal_path)
    journal.append(
        cx.TextReplace(node_id="p:1", before="a", after="b"),
        _target("p:1"),
        _prov(journal, agent="claude-opus-4-8", vendor="anthropic", provenance_source="declared"),
    )
    (event,) = list(journal.read())
    assert event.provenance.agent == "claude-opus-4-8"
    assert event.provenance.vendor == "anthropic"
    assert event.provenance.provenance_source == "declared"


# --------------------------------------------------------------------------- #
# Replay equivalence
# --------------------------------------------------------------------------- #
def test_replay_reproduces_live_model(journal_path: Path) -> None:
    adapter = FakeAdapter([("p:1", "the quick brown fox")])
    baseline = cx.Node.from_dict(adapter.to_model().to_dict())
    journal = _open_journal(journal_path)
    ops = [
        cx.TextReplace(node_id="p:1", before="quick", after="swift"),
        cx.TextInsert(node_id="p:1", before_anchor="fox", text=" today"),
    ]
    for op in ops:
        adapter.apply(op)
        journal.append(op, _target("p:1"), _prov(journal))
    live_text = adapter.to_model().find("p:1").text()

    fresh = FakeAdapter([("p:1", "the quick brown fox")])
    replayed = journal.replay(fresh, baseline)
    assert replayed.find("p:1").text() == live_text == "the swift brown fox today"


# --------------------------------------------------------------------------- #
# Revert (per-op reject) — including a MIDDLE op
# --------------------------------------------------------------------------- #
def test_revert_middle_op_leaves_others_resolving(journal_path: Path) -> None:
    adapter = FakeAdapter([("p:1", "the quick brown lazy fox")])
    baseline = cx.Node.from_dict(adapter.to_model().to_dict())
    journal = _open_journal(journal_path)
    e1 = journal.append(
        cx.TextReplace(node_id="p:1", before="quick", after="swift"), _target("p:1"), _prov(journal)
    )
    e2 = journal.append(
        cx.TextReplace(node_id="p:1", before="lazy", after="sleepy"), _target("p:1"), _prov(journal)
    )
    e3 = journal.append(
        cx.TextInsert(node_id="p:1", before_anchor="fox", text=" today"), _target("p:1"), _prov(journal)
    )
    # Reject the MIDDLE op (lazy -> sleepy).
    journal.revert(e2.op_id)
    assert journal.is_reverted(e2.op_id)
    assert not journal.is_reverted(e1.op_id)

    active = journal.active_events()
    assert [e.op_id for e in active] == [e1.op_id, e3.op_id]

    fresh = FakeAdapter([("p:1", "the quick brown lazy fox")])
    replayed = journal.replay(fresh, baseline)
    # 'swift' kept, 'lazy' restored (revert), ' today' kept.
    assert replayed.find("p:1").text() == "the swift brown lazy fox today"


def test_revert_is_audited_and_survives_reopen(journal_path: Path) -> None:
    journal = _open_journal(journal_path)
    e1 = journal.append(
        cx.TextReplace(node_id="p:1", before="a", after="b"), _target("p:1"), _prov(journal)
    )
    journal.revert(e1.op_id)
    # The revert marker is its own line — verify() must still pass (op lines OK).
    assert journal.verify().ok
    reopened = cx.Journal.open(str(journal.path))
    assert reopened.is_reverted(e1.op_id)
    assert reopened.active_events() == []


def test_revert_unknown_op_raises(journal_path: Path) -> None:
    journal = _open_journal(journal_path)
    with pytest.raises(cx.JournalError):
        journal.revert("does-not-exist")


# --------------------------------------------------------------------------- #
# Verify: clean chain + tamper detection
# --------------------------------------------------------------------------- #
def test_verify_ok_on_clean_chain(journal_path: Path) -> None:
    journal = _open_journal(journal_path)
    for i in range(4):
        journal.append(
            cx.TextInsert(node_id="p:1", before_anchor=None, text=str(i)),
            _target("p:1"),
            _prov(journal),
        )
    result = journal.verify()
    assert result.ok
    assert result.broken_at_seq is None


def test_verify_detects_tampered_op_payload(journal_path: Path) -> None:
    journal = _open_journal(journal_path)
    journal.append(
        cx.TextReplace(node_id="p:1", before="a", after="b"), _target("p:1"), _prov(journal)
    )
    journal.append(
        cx.TextReplace(node_id="p:1", before="b", after="c"), _target("p:1"), _prov(journal)
    )
    # Tamper with the FIRST event's op payload, leaving its stored hash intact.
    lines = journal.path.read_text(encoding="utf-8").splitlines()
    event1 = json.loads(lines[1])
    event1["op"]["after"] = "HACKED"
    lines[1] = json.dumps(event1, ensure_ascii=False)
    journal.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = cx.Journal.open(str(journal.path)).verify()
    assert result.ok is False
    assert result.broken_at_seq == 1


def test_verify_detects_broken_prev_hash_link(journal_path: Path) -> None:
    journal = _open_journal(journal_path)
    journal.append(
        cx.TextReplace(node_id="p:1", before="a", after="b"), _target("p:1"), _prov(journal)
    )
    journal.append(
        cx.TextReplace(node_id="p:1", before="b", after="c"), _target("p:1"), _prov(journal)
    )
    lines = journal.path.read_text(encoding="utf-8").splitlines()
    event2 = json.loads(lines[2])
    event2["prev_hash"] = "deadbeef" * 8  # break the chain link, keep own hash
    lines[2] = json.dumps(event2, ensure_ascii=False)
    journal.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = cx.Journal.open(str(journal.path)).verify()
    assert result.ok is False
    assert result.broken_at_seq == 2


# --------------------------------------------------------------------------- #
# Canonicalization (JCS): key-order independence + chaining
# --------------------------------------------------------------------------- #
def test_canonicalize_is_key_order_independent() -> None:
    a = {"b": 1, "a": [1, 2, {"z": True, "y": None}], "c": "x"}
    b = {"c": "x", "a": [1, 2, {"y": None, "z": True}], "b": 1}
    assert cx.canonicalize(a) == cx.canonicalize(b)
    # And it is the byte-sorted canonical form.
    assert cx.canonicalize(a) == b'{"a":[1,2,{"y":null,"z":true}],"b":1,"c":"x"}'


def test_chain_hash_changes_with_content_and_prev() -> None:
    event = {"type": "op", "seq": 1, "op": {"kind": "text.delete", "before": "x"}}
    h_genesis = cx.chain_hash(None, event)
    h_linked = cx.chain_hash(h_genesis, event)
    assert h_genesis != h_linked
    mutated = dict(event, seq=2)
    assert cx.chain_hash(None, mutated) != h_genesis
    assert len(h_genesis) == 64  # sha256 hex
