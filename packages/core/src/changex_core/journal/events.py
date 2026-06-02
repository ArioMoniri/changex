"""Header + Event (op) dataclasses with provenance split observed vs declared.

Provenance is deliberately layered (per the tech-lead decision):

* **observed** — what the server can populate from call context:
  ``ts``, ``session_id``, ``tool_call_id``, ``client_name``/``client_version``.
* **declared** — what only the agent can supply (and is therefore optional and
  may be ``null``): ``agent`` (model id), ``vendor``, ``turn_id``,
  ``prompt_sha256``, ``rationale``.

``provenance_source`` labels which layer dominated, so journals never present a
declared value as if the server observed it. We do **not** key anything on
``tool_call_id``; identity is ``session_id`` + server-assigned ``seq``.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from changex_core.ops.vocabulary import OP_SCHEMA_VERSION

CHANGEX_VERSION = "0.1"
ProvenanceSource = Literal["observed", "declared"]


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a ``Z`` suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def new_id() -> str:
    """Return a fresh random uuid4 hex-dashed string (for op_id / session_id)."""
    return str(uuid.uuid4())


@dataclass
class Provenance:
    """Attribution for one operation, split observed vs declared."""

    ts: str
    session_id: str
    tool_call_id: Optional[str] = None
    client_name: Optional[str] = None
    client_version: Optional[str] = None
    agent: Optional[str] = None
    vendor: Optional[str] = None
    turn_id: Optional[str] = None
    prompt_sha256: Optional[str] = None
    rationale: Optional[str] = None
    provenance_source: ProvenanceSource = "observed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Provenance":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Target:
    """The addressed node for an operation (node_id is the durable identity)."""

    node_id: str
    node_kind: str
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Target":
        return cls(
            node_id=str(data["node_id"]),
            node_kind=str(data["node_kind"]),
            path=str(data.get("path", "")),
        )


@dataclass
class Header:
    """The ``.changex`` header line (line 1 of the JSONL file)."""

    changex_version: str = CHANGEX_VERSION
    op_schema_version: str = OP_SCHEMA_VERSION
    doc: dict[str, Any] = field(default_factory=dict)
    session: dict[str, Any] = field(default_factory=dict)
    node_id_map: dict[str, str] = field(default_factory=dict)
    prev_hash: None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "header",
            "changex_version": self.changex_version,
            "op_schema_version": self.op_schema_version,
            "doc": dict(self.doc),
            "session": dict(self.session),
            "node_id_map": dict(self.node_id_map),
            "prev_hash": None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Header":
        return cls(
            changex_version=str(data.get("changex_version", CHANGEX_VERSION)),
            op_schema_version=str(data.get("op_schema_version", OP_SCHEMA_VERSION)),
            doc=dict(data.get("doc", {})),
            session=dict(data.get("session", {})),
            node_id_map=dict(data.get("node_id_map", {})),
        )

    @classmethod
    def create(
        cls,
        *,
        baseline_sha256: str,
        filename: Optional[str] = None,
        doc_format: str = "docx",
        baseline_uri: Optional[str] = None,
        session_id: Optional[str] = None,
        capture_mode: str = "active",
        node_id_map: Optional[dict[str, str]] = None,
    ) -> "Header":
        """Build a header from the common open-time fields."""
        return cls(
            doc={
                "filename": filename,
                "format": doc_format,
                "baseline_sha256": baseline_sha256,
                "baseline_uri": baseline_uri,
            },
            session={
                "session_id": session_id or new_id(),
                "started_at": utc_now_iso(),
                "capture_mode": capture_mode,
            },
            node_id_map=dict(node_id_map or {}),
        )

    @property
    def session_id(self) -> str:
        return str(self.session.get("session_id", ""))

    @property
    def baseline_sha256(self) -> str:
        return str(self.doc.get("baseline_sha256", ""))


@dataclass
class Event:
    """One operation event line (lines 2..N of the JSONL file)."""

    op_id: str
    seq: int
    ts: str
    provenance: Provenance
    target: Target
    op: dict[str, Any]
    hash: str
    prev_hash: Optional[str]
    op_schema_version: str = OP_SCHEMA_VERSION

    def content_dict(self) -> dict[str, Any]:
        """The hashable content of the event (excludes hash/prev_hash).

        This is exactly what is fed to :func:`chain_hash`. The ordering does not
        matter — JCS sorts keys — but the *set* of fields is part of the contract.
        """
        return {
            "type": "op",
            "op_id": self.op_id,
            "seq": self.seq,
            "ts": self.ts,
            "op_schema_version": self.op_schema_version,
            "provenance": self.provenance.to_dict(),
            "target": self.target.to_dict(),
            "op": self.op,
        }

    def to_dict(self) -> dict[str, Any]:
        """Full on-disk line dict (content + hash + prev_hash)."""
        data = self.content_dict()
        data["hash"] = self.hash
        data["prev_hash"] = self.prev_hash
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(
            op_id=str(data["op_id"]),
            seq=int(data["seq"]),
            ts=str(data["ts"]),
            op_schema_version=str(data.get("op_schema_version", OP_SCHEMA_VERSION)),
            provenance=Provenance.from_dict(data["provenance"]),
            target=Target.from_dict(data["target"]),
            op=dict(data["op"]),
            hash=str(data["hash"]),
            prev_hash=data.get("prev_hash"),
        )
