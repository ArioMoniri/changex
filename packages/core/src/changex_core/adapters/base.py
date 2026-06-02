"""The ``DocumentAdapter`` contract every format adapter implements.

This abstract interface is the anti-drift contract between the journal/render
layer and each format. The journal calls only these methods, so a new format
(xlsx, pptx) plugs in without touching journal or render code.

Key invariants an implementation must uphold:

* ``to_model()`` returns a tree whose ``node_id``s are **opaque and
  edit-invariant** (never content hashes).
* ``apply(op)`` mutates the in-memory model and **raises on a before-mismatch or
  an oversized op** (the validation the MCP boundary also performs, enforced here
  so direct/core callers get the same guarantee).
* ``render_tracked()`` returns native tracked-changes bytes (for docx: real
  ``w:ins``/``w:del`` revisions a Word/LibreOffice user can accept/reject).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from changex_core.model.nodes import Node
from changex_core.ops.vocabulary import Op


class AdapterError(RuntimeError):
    """Base error for adapter operations."""


class BeforeMismatchError(AdapterError):
    """Raised when an op's ``before`` substring is not present in the node.

    This is the boundary guard that kills blind full-node overwrites: the agent
    must pass the exact text it intends to change, and the adapter refuses if the
    node's current content does not contain it.
    """


class OversizedOpError(AdapterError):
    """Raised when an op rewrites too much of a node or spans more than one node.

    The structured message instructs the caller to split the change — the error
    message is itself the prompt the model should act on.
    """


class NodeNotFoundError(AdapterError):
    """Raised when an op targets a ``node_id`` not present in the model."""


class DocumentAdapter(ABC):
    """Abstract base for format adapters (docx implemented; others reserved)."""

    @classmethod
    @abstractmethod
    def load(cls, path: str) -> "DocumentAdapter":
        """Load a document from a (sanitized) path and build the model."""
        raise NotImplementedError

    @abstractmethod
    def baseline_sha256(self) -> str:
        """Return the sha256 of the original document bytes captured on load."""
        raise NotImplementedError

    @abstractmethod
    def to_model(self) -> Node:
        """Return the current canonical model tree (root node)."""
        raise NotImplementedError

    @abstractmethod
    def set_model(self, root: Node) -> None:
        """Reset the adapter's working state to ``root`` (used by replay)."""
        raise NotImplementedError

    @abstractmethod
    def resolve(self, node_id: str) -> Node | None:
        """Return the model node with ``node_id``, or ``None`` if absent."""
        raise NotImplementedError

    @abstractmethod
    def apply(self, op: Op) -> None:
        """Apply one op to the model.

        Raises:
            BeforeMismatchError: if the op's ``before`` is absent.
            OversizedOpError: if the op is too large / multi-node.
            NodeNotFoundError: if the target node is missing.
        """
        raise NotImplementedError

    @abstractmethod
    def render_tracked(self) -> bytes:
        """Render the applied ops as native tracked-changes bytes."""
        raise NotImplementedError

    @abstractmethod
    def save(self, out_path: str) -> None:
        """Write the tracked document to a (sanitized) ``out_path``."""
        raise NotImplementedError
