"""Canonical document-model node tree.

The model is a normalized, addressable tree shared by every adapter so that
operations and provenance are format-agnostic. Each :class:`Node` carries an
**opaque, edit-invariant** ``node_id`` (see
:mod:`changex_core.model.addressing` for the allocation strategy) — it is
explicitly *not* a content hash, because content hashes mutate on exactly the
edits ChangeX exists to track.

For the docx MVP the node kinds are ``paragraph``, ``run`` and ``style``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Optional


class NodeKind(str, Enum):
    """The canonical node kinds for the docx MVP.

    The string value is what is persisted in journal ``target.node_kind`` and op
    ``node_kind`` fields, so these values are part of the on-disk contract.
    """

    DOCUMENT = "document"
    PARAGRAPH = "paragraph"
    RUN = "run"
    STYLE = "style"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass
class Node:
    """One addressable node in the canonical document tree.

    Attributes:
        node_id: Opaque, edit-invariant identifier. For docx paragraphs this is
            derived from Word's native ``w14:paraId``; for nodes lacking a native
            id it is a minted monotonic counter. Never a content hash.
        node_kind: The :class:`NodeKind` of this node.
        path: A human-readable, *advisory* locator (e.g. ``/body/p[7]``). Not used
            for addressing — it is debugging/UX sugar only.
        value: The node's primary scalar value. For paragraphs/runs this is the
            text content; for style nodes it is the style name.
        attrs: Format-specific attributes (e.g. ``{"style": "Heading 2"}``).
        children: Child nodes (e.g. runs under a paragraph).
    """

    node_id: str
    node_kind: NodeKind
    path: str = ""
    value: Any = None
    attrs: dict[str, Any] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)

    # -- tree helpers ---------------------------------------------------------

    def walk(self) -> Iterator["Node"]:
        """Yield this node then every descendant, depth-first (pre-order)."""
        yield self
        for child in self.children:
            yield from child.walk()

    def find(self, node_id: str) -> Optional["Node"]:
        """Return the node in this subtree with ``node_id``, or ``None``."""
        for node in self.walk():
            if node.node_id == node_id:
                return node
        return None

    def text(self) -> str:
        """Return the concatenated text of this node and its run children.

        For a paragraph this reconstructs the full paragraph text from its runs;
        for a run/leaf it returns ``value`` coerced to ``str``.
        """
        if self.node_kind in (NodeKind.PARAGRAPH, NodeKind.DOCUMENT) and self.children:
            return "".join(
                child.text() for child in self.children if child.node_kind == NodeKind.RUN
            )
        return "" if self.value is None else str(self.value)

    def child_paragraphs(self) -> list["Node"]:
        """Return immediate paragraph children (document body convenience)."""
        return [c for c in self.children if c.node_kind == NodeKind.PARAGRAPH]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the subtree to a plain dict (used by snapshots/replay)."""
        return {
            "node_id": self.node_id,
            "node_kind": self.node_kind.value,
            "path": self.path,
            "value": self.value,
            "attrs": dict(self.attrs),
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Node":
        """Reconstruct a :class:`Node` subtree from :meth:`to_dict` output."""
        return cls(
            node_id=str(data["node_id"]),
            node_kind=NodeKind(data["node_kind"]),
            path=str(data.get("path", "")),
            value=data.get("value"),
            attrs=dict(data.get("attrs", {})),
            children=[cls.from_dict(c) for c in data.get("children", [])],
        )


def clone(node: Node) -> Node:
    """Deep-copy a node subtree without sharing mutable state.

    Used by replay so a baseline model can be mutated independently of the live
    model the adapter holds.
    """
    return Node.from_dict(node.to_dict())
