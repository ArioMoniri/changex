"""The append-only ``.changex`` Journal: append / read / replay / verify / revert.

The journal is a JSONL file: line 1 is the header, lines 2..N are op events. Each
append assigns a monotonic ``seq``, computes ``hash = chain_hash(prev_hash,
content)``, schema-validates, and **flushes to disk immediately** so a crash
loses at most one in-flight op.

Replay reconstructs the saved document by applying events in strict ``seq``
order onto a baseline model via a :class:`DocumentAdapter`. ``revert`` marks one
op as rejected (without rewriting history) so its revision element is dropped on
the next render/replay — i.e. rejection is non-destructive to the audit trail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Optional

from changex_core.journal.canonical import chain_hash
from changex_core.journal.events import Event, Header, Provenance, Target, new_id, utc_now_iso
from changex_core.ops.validation import validate_event, validate_header
from changex_core.ops.vocabulary import Op, op_to_dict
from changex_core.paths import safe_path

if TYPE_CHECKING:  # avoid an import cycle; only needed for typing
    from changex_core.adapters.base import DocumentAdapter
    from changex_core.model.nodes import Node


class JournalError(RuntimeError):
    """Base error for journal operations."""


class VerifyResult:
    """Outcome of :meth:`Journal.verify`."""

    def __init__(
        self,
        ok: bool,
        broken_at_seq: Optional[int] = None,
        baseline_match: bool = True,
        detail: str = "",
    ) -> None:
        self.ok = ok
        self.broken_at_seq = broken_at_seq
        self.baseline_match = baseline_match
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"VerifyResult(ok={self.ok}, broken_at_seq={self.broken_at_seq}, "
            f"baseline_match={self.baseline_match})"
        )


class Journal:
    """An append-only JSONL provenance journal with a sha256 hash chain."""

    def __init__(self, path: Path, header: Header) -> None:
        self._path = path
        self._header = header
        self._seq = 0
        self._last_hash: Optional[str] = None
        self._reverted: set[str] = set()

    # -- lifecycle ------------------------------------------------------------

    @classmethod
    def open(cls, path: str, header: Optional[Header] = None) -> "Journal":
        """Open or create a journal at ``path``.

        If the file exists it is loaded (header + chain state recovered). If it
        does not exist, ``header`` is required and written as line 1.
        """
        resolved = safe_path(path, allow_suffixes=(".changex", ".jsonl"))
        if resolved.exists():
            journal = cls._load_existing(resolved)
            return journal
        if header is None:
            raise JournalError("creating a new journal requires a header")
        validate_header(header.to_dict())
        resolved.parent.mkdir(parents=True, exist_ok=True)
        journal = cls(resolved, header)
        with resolved.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(header.to_dict(), ensure_ascii=False) + "\n")
            fh.flush()
        return journal

    @classmethod
    def _load_existing(cls, resolved: Path) -> "Journal":
        lines = resolved.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise JournalError(f"journal {resolved} is empty")
        header = Header.from_dict(json.loads(lines[0]))
        validate_header(header.to_dict())
        journal = cls(resolved, header)
        for raw in lines[1:]:
            raw = raw.strip()
            if not raw:
                continue
            data = json.loads(raw)
            if data.get("type") == "revert":
                journal._reverted.add(str(data["op_id"]))
                continue
            if data.get("type") == "unrevert":
                journal._reverted.discard(str(data["op_id"]))
                continue
            event = Event.from_dict(data)
            journal._seq = event.seq
            journal._last_hash = event.hash
        return journal

    # -- accessors ------------------------------------------------------------

    @property
    def header(self) -> Header:
        return self._header

    @property
    def path(self) -> Path:
        return self._path

    @property
    def last_seq(self) -> int:
        return self._seq

    def is_reverted(self, op_id: str) -> bool:
        """Return whether ``op_id`` has been rejected via :meth:`revert`."""
        return op_id in self._reverted

    # -- append ---------------------------------------------------------------

    def append(self, op: Op, target: Target, provenance: Provenance) -> Event:
        """Append one op, assigning seq + hash, validating, and flushing.

        Returns the persisted :class:`Event`. The ``seq`` is server-assigned
        (monotonic), never taken from the caller, so concurrent callers cannot
        corrupt ordering.
        """
        self._seq += 1
        event = Event(
            op_id=new_id(),
            seq=self._seq,
            ts=utc_now_iso(),
            provenance=provenance,
            target=target,
            op=op_to_dict(op),
            hash="",
            prev_hash=self._last_hash,
        )
        event.hash = chain_hash(self._last_hash, event.content_dict())
        line_dict = event.to_dict()
        validate_event(line_dict)
        self._append_line(line_dict)
        self._last_hash = event.hash
        return event

    def revert(self, op_id: str) -> None:
        """Reject one op by id without rewriting history.

        A ``revert`` marker line is appended (so the action is itself audited);
        the reverted op is then skipped by :meth:`replay` and render.
        """
        known = {e.op_id for e in self.read()}
        if op_id not in known:
            raise JournalError(f"cannot revert unknown op_id {op_id!r}")
        self._reverted.add(op_id)
        self._append_line({"type": "revert", "op_id": op_id, "ts": utc_now_iso()})

    def unrevert(self, op_id: str) -> None:
        """Un-reject a previously reverted op by id (the accept side of review).

        Like :meth:`revert`, this is non-destructive and itself audited: an
        ``unrevert`` marker line is appended so the accept action is traceable,
        and the op rejoins :meth:`active_events` / :meth:`replay`. Un-reverting an
        op that is not currently reverted is a no-op (no marker written).
        """
        known = {e.op_id for e in self.read()}
        if op_id not in known:
            raise JournalError(f"cannot unrevert unknown op_id {op_id!r}")
        if op_id not in self._reverted:
            return
        self._reverted.discard(op_id)
        self._append_line({"type": "unrevert", "op_id": op_id, "ts": utc_now_iso()})

    def _append_line(self, data: dict[str, Any]) -> None:
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(data, ensure_ascii=False) + "\n")
            fh.flush()

    # -- read -----------------------------------------------------------------

    def read(self) -> Iterator[Event]:
        """Yield every op :class:`Event` in seq order (skips header/revert lines)."""
        lines = self._path.read_text(encoding="utf-8").splitlines()
        for raw in lines[1:]:
            raw = raw.strip()
            if not raw:
                continue
            data = json.loads(raw)
            if data.get("type") != "op":
                continue
            yield Event.from_dict(data)

    def active_events(self) -> list[Event]:
        """Return non-reverted events sorted by seq (the replayable set)."""
        events = [e for e in self.read() if e.op_id not in self._reverted]
        events.sort(key=lambda e: e.seq)
        return events

    # -- replay / verify ------------------------------------------------------

    def replay(self, adapter: "DocumentAdapter", baseline: "Node") -> "Node":
        """Replay active events onto ``baseline`` via ``adapter``.

        Replay is strictly seq-ordered. ``adapter`` is reset to ``baseline``
        first, then each non-reverted op is applied; the resulting model is
        returned. Reverted ops are skipped, so a middle-op rejection leaves all
        other ops resolving correctly.
        """
        from changex_core.ops.vocabulary import op_from_dict

        adapter.set_model(baseline)
        for event in self.active_events():
            adapter.apply(op_from_dict(event.op))
        return adapter.to_model()

    def verify(self, baseline_path: Optional[str] = None) -> VerifyResult:
        """Recompute the hash chain and check it matches what is on disk.

        Returns a :class:`VerifyResult`; ``broken_at_seq`` points at the first
        event whose recomputed hash disagrees (tamper-evidence). This does not
        guard against an adversary who rewrote the whole chain — see the threat
        model in :mod:`changex_core.journal.canonical`.

        If ``baseline_path`` (or, failing that, the header's recorded
        ``baseline_uri``) resolves to a readable file, its sha256 is recomputed
        and compared against the header ``baseline_sha256`` to set
        ``baseline_match`` — proving the journal is still bound to the exact
        document it was opened against. When no baseline is available
        ``baseline_match`` stays ``True`` (unknown is not a failure) and the
        detail notes it was unchecked.
        """
        prev: Optional[str] = None
        for event in self.read():
            expected = chain_hash(prev, event.content_dict())
            if expected != event.hash:
                return VerifyResult(
                    ok=False,
                    broken_at_seq=event.seq,
                    detail=f"hash mismatch at seq={event.seq}",
                )
            if event.prev_hash != prev:
                return VerifyResult(
                    ok=False,
                    broken_at_seq=event.seq,
                    detail=f"prev_hash break at seq={event.seq}",
                )
            prev = event.hash

        baseline_match, detail = self._check_baseline(baseline_path)
        # ``ok`` reflects chain integrity (intact here); ``baseline_match`` is a
        # separate axis so a caller can distinguish "tampered chain" from
        # "document drifted from its baseline".
        return VerifyResult(ok=True, baseline_match=baseline_match, detail=detail)

    def _check_baseline(self, baseline_path: Optional[str]) -> tuple[bool, str]:
        """Re-hash the on-disk baseline against the header ``baseline_sha256``.

        Returns ``(baseline_match, detail)``. A missing/unreadable baseline is
        reported as ``(True, "baseline not checked: ...")`` — unknown is not a
        chain failure — while a present-but-mismatched baseline is a hard
        ``(False, ...)``.
        """
        from changex_core.journal.canonical import sha256_hex
        from changex_core.paths import UnsafePathError, safe_path

        expected = self._header.baseline_sha256
        if not expected:
            return True, "baseline not checked: header has no baseline_sha256"

        candidate = baseline_path or self._header.doc.get("baseline_uri")
        if not candidate:
            return True, "baseline not checked: no baseline path or header baseline_uri"
        try:
            resolved = safe_path(str(candidate), must_exist=True)
            actual = sha256_hex(resolved.read_bytes())
        except (UnsafePathError, OSError) as exc:
            return True, f"baseline not checked: {exc}"

        if actual == expected:
            return True, "baseline matches header baseline_sha256"
        return False, (
            f"baseline mismatch: on-disk sha256 {actual[:12]}… != "
            f"header {expected[:12]}… (document changed out of band)"
        )
