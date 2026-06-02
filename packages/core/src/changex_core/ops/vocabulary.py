"""Frozen v0.1 operation vocabulary (docx-only).

This is the shared op set that both the adapter and the (separate) MCP package
build on. It is deliberately small and intent-named — the path of least
resistance for a model must still produce small, attributable ops.

Design rules baked in here:

* Text offsets are **node-relative** and **seq-ordered** — never absolute file
  coordinates. We address by ``node_id`` and validate the agent-supplied
  ``before`` substring against the node's *current* state.
* Each op carries the prior ``before`` / ``value`` it needs to be **rejected or
  replayed without the original file** (reversibility invariant).
* ``node_kind`` (not ``kind_of``) names the target structural type — resolving
  the historic ``kind`` / ``kind_of`` overload.

DEFERRED (not in v0.1): ``format.run``, ``node.move``, and all xlsx/pptx/csv ops
(reserved appendix). Constructing those from this set raises
:class:`ReservedOpError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Union

OP_SCHEMA_VERSION = "0.1"

# Kinds that are reserved but not implemented in v0.1; rejected at parse time.
_RESERVED_KINDS = frozenset(
    {
        "format.run",
        "node.move",
        "cell.set",
        "formula.set",
        "row.insert",
        "row.delete",
        "slide.insert",
        "slide.delete",
        "shape.edit",
    }
)


class ReservedOpError(ValueError):
    """Raised when a journal references an op kind reserved for a later version."""


class UnknownOpError(ValueError):
    """Raised when an op ``kind`` is neither a v0.1 op nor a reserved one."""


@dataclass(frozen=True)
class TextInsert:
    """Insert ``text`` after the ``before_anchor`` substring within a node.

    If ``before_anchor`` is ``None`` the text is appended at the end of the node.
    Rendered as ``w:ins > w:r > w:t``.
    """

    node_id: str
    before_anchor: str | None
    text: str
    kind: ClassVar[str] = "text.insert"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "node_id": self.node_id,
            "before_anchor": self.before_anchor,
            "text": self.text,
        }


@dataclass(frozen=True)
class TextDelete:
    """Delete the exact ``before`` substring from a node.

    ``before`` is validated against current node content. Rendered as
    ``w:del > w:r > w:delText``.
    """

    node_id: str
    before: str
    kind: ClassVar[str] = "text.delete"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "node_id": self.node_id, "before": self.before}


@dataclass(frozen=True)
class TextReplace:
    """Replace the exact ``before`` substring with ``after`` within a node.

    Rendered as a ``w:del``(delText) immediately followed by a ``w:ins``(t).
    """

    node_id: str
    before: str
    after: str
    kind: ClassVar[str] = "text.replace"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "node_id": self.node_id,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class NodeInsert:
    """Insert a new structural node (a paragraph for v0.1) at ``position``.

    ``value`` is the node payload, e.g. ``{"text": "...", "style": "Normal"}``.
    The inserted paragraph mark is rendered as a pilcrow-insertion revision.
    """

    node_kind: str
    position: int
    value: dict[str, Any]
    kind: ClassVar[str] = "node.insert"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "node_kind": self.node_kind,
            "position": self.position,
            "value": dict(self.value),
        }


@dataclass(frozen=True)
class NodeDelete:
    """Delete a structural node, capturing its ``value`` for reject/replay.

    Rendered by marking the node's runs as ``w:del`` and the paragraph mark as a
    pilcrow-deletion revision.
    """

    node_id: str
    value: dict[str, Any]
    kind: ClassVar[str] = "node.delete"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "node_id": self.node_id, "value": dict(self.value)}


@dataclass(frozen=True)
class StyleChange:
    """Change a paragraph's style, capturing the prior ``before`` style name.

    Rendered as a ``w:pPrChange`` carrying the previous paragraph properties.
    """

    node_id: str
    style: str
    before: str
    kind: ClassVar[str] = "style.change"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "node_id": self.node_id,
            "style": self.style,
            "before": self.before,
        }


Op = Union[TextInsert, TextDelete, TextReplace, NodeInsert, NodeDelete, StyleChange]

_BY_KIND: dict[str, type] = {
    TextInsert.kind: TextInsert,
    TextDelete.kind: TextDelete,
    TextReplace.kind: TextReplace,
    NodeInsert.kind: NodeInsert,
    NodeDelete.kind: NodeDelete,
    StyleChange.kind: StyleChange,
}

V01_KINDS = frozenset(_BY_KIND.keys())


def op_to_dict(op: Op) -> dict[str, Any]:
    """Serialize any v0.1 op to its journal dict form."""
    return op.to_dict()


def op_from_dict(data: dict[str, Any]) -> Op:
    """Reconstruct a v0.1 op from its dict form.

    Raises:
        ReservedOpError: if ``kind`` is a reserved-but-unimplemented op.
        UnknownOpError: if ``kind`` is not recognised at all.
    """
    kind = data.get("kind")
    if kind in _RESERVED_KINDS:
        raise ReservedOpError(
            f"op kind {kind!r} is reserved and not implemented in v{OP_SCHEMA_VERSION}"
        )
    cls = _BY_KIND.get(kind or "")
    if cls is None:
        raise UnknownOpError(f"unknown op kind {kind!r}")
    payload = {k: v for k, v in data.items() if k != "kind"}
    return cls(**payload)  # type: ignore[arg-type]


def target_node_id(op: Op) -> str | None:
    """Return the ``node_id`` an op targets, or ``None`` for ``node.insert``."""
    return getattr(op, "node_id", None)
