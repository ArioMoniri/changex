"""Canonical document model: addressable nodes + opaque edit-invariant ids."""

from __future__ import annotations

from changex_core.model.addressing import (
    AnchorFingerprint,
    NodeIdAllocator,
    RebindResult,
    normalize_text,
    rebind,
)
from changex_core.model.nodes import Node, NodeKind, clone

__all__ = [
    "Node",
    "NodeKind",
    "clone",
    "NodeIdAllocator",
    "AnchorFingerprint",
    "RebindResult",
    "rebind",
    "normalize_text",
]
