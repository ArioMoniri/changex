"""Stable, edit-invariant node addressing.

This module implements the linchpin decision: ``node_id`` is **opaque** and
**edit-invariant**, decoupled from content.

Strategy
--------
1. **docx paragraphs** reuse Word's native ``w14:paraId`` (a 32-bit stable id
   Word preserves across edits). The adapter passes the paraId in; we namespace
   it as ``p:<paraId>``.
2. **Sub-paragraph / native-id-less nodes** get a minted **monotonic per-session
   counter** (``r:000123``) recorded at first sight. The adapter is responsible
   for persisting the carrier (a ``w:bookmarkStart``/``w:bookmarkEnd`` pair) so
   the id survives a save/reload round-trip.
3. The content+position **fingerprint** is *demoted* to a secondary
   :class:`AnchorFingerprint` used **only** for fuzzy re-resolution when a sidecar
   is lost or after out-of-band edits, emitting an explicit ``rebind`` result
   with a confidence score (low confidence is surfaced, never silently
   mis-attributed).

The paraId<->node_id mapping is persisted in the ``.changex`` header
(``node_id_map``) so a future reader can reconcile.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

PARA_ID_PREFIX = "p"
RUN_ID_PREFIX = "r"
GENERIC_ID_PREFIX = "n"

# Confidence thresholds for fuzzy rebind. Anything at/above HIGH is trusted;
# between LOW and HIGH is surfaced as a low-confidence rebind; below LOW is a miss.
REBIND_HIGH_CONFIDENCE = 0.85
REBIND_LOW_CONFIDENCE = 0.55


def normalize_text(text: str) -> str:
    """Return an NFC-normalized, whitespace-collapsed, lowercased fingerprint key.

    Used only for the *secondary* rebind anchor — never for the primary id.
    """
    norm = unicodedata.normalize("NFC", text or "")
    norm = re.sub(r"\s+", " ", norm).strip().lower()
    return norm


class NodeIdAllocator:
    """Per-session allocator: reuses native paraIds, mints monotonic counters.

    The allocator is the single source of truth for the ``node_id <-> carrier``
    mapping within a session. It is deterministic given the same call order, so
    replay reproduces the same ids.
    """

    def __init__(self, start: int = 0) -> None:
        self._counter = start
        # node_id -> carrier (paraId for paragraphs, bookmark name for runs)
        self._carriers: dict[str, str] = {}
        # carrier -> node_id reverse lookup (so re-seeing a paraId reuses its id)
        self._by_carrier: dict[str, str] = {}

    # -- paragraph ids (native paraId reuse) ----------------------------------

    def for_para_id(self, para_id: Optional[str]) -> str:
        """Return a stable node_id for a docx paragraph given its ``w14:paraId``.

        If ``para_id`` is ``None`` (the generator omitted paraIds), a monotonic
        counter id is minted instead and recorded so it can be injected back.
        """
        if para_id:
            carrier = str(para_id).upper()
            existing = self._by_carrier.get(carrier)
            if existing is not None:
                return existing
            node_id = f"{PARA_ID_PREFIX}:{carrier}"
            self._register(node_id, carrier)
            return node_id
        return self.mint(PARA_ID_PREFIX)

    # -- minted ids (runs / id-less nodes) ------------------------------------

    def mint(self, prefix: str = RUN_ID_PREFIX) -> str:
        """Mint a fresh monotonic node_id and a matching carrier (bookmark name)."""
        self._counter += 1
        node_id = f"{prefix}:{self._counter:06d}"
        carrier = f"changex_{prefix}_{self._counter:06d}"
        self._register(node_id, carrier)
        return node_id

    def _register(self, node_id: str, carrier: str) -> None:
        self._carriers[node_id] = carrier
        self._by_carrier[carrier] = node_id

    # -- mapping persistence --------------------------------------------------

    def carrier_for(self, node_id: str) -> Optional[str]:
        """Return the carrier (paraId / bookmark name) for ``node_id``."""
        return self._carriers.get(node_id)

    def node_id_for_carrier(self, carrier: str) -> Optional[str]:
        """Return the node_id registered for ``carrier``, or ``None``."""
        return self._by_carrier.get(carrier)

    def as_map(self) -> dict[str, str]:
        """Return the ``node_id -> carrier`` map for the ``.changex`` header."""
        return dict(self._carriers)

    @classmethod
    def from_map(cls, mapping: dict[str, str], start: int = 0) -> "NodeIdAllocator":
        """Rebuild an allocator from a persisted header map.

        ``start`` should be the high-water mark of previously minted counters so
        new mints do not collide with persisted ids.
        """
        alloc = cls(start=start)
        for node_id, carrier in mapping.items():
            alloc._register(node_id, carrier)
        return alloc


@dataclass
class AnchorFingerprint:
    """A *secondary* fuzzy-rebind anchor — never the primary identity.

    Captured at first sight so that, if the id<->carrier mapping is later lost
    (sidecar deleted, out-of-band edit), a node can be re-resolved by content +
    position with an explicit confidence score.
    """

    para_id: Optional[str]
    char_range: tuple[int, int]
    normalized_text_fp: str
    sibling_context: tuple[str, str] = ("", "")  # (prev normalized text, next)

    @classmethod
    def of(
        cls,
        text: str,
        *,
        para_id: Optional[str] = None,
        char_range: Optional[tuple[int, int]] = None,
        prev_text: str = "",
        next_text: str = "",
    ) -> "AnchorFingerprint":
        """Build an anchor fingerprint from a node's text and its neighbours."""
        rng = char_range if char_range is not None else (0, len(text or ""))
        return cls(
            para_id=str(para_id).upper() if para_id else None,
            char_range=rng,
            normalized_text_fp=normalize_text(text),
            sibling_context=(normalize_text(prev_text), normalize_text(next_text)),
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize for storage in the journal header."""
        return {
            "para_id": self.para_id,
            "char_range": list(self.char_range),
            "normalized_text_fp": self.normalized_text_fp,
            "sibling_context": list(self.sibling_context),
        }


@dataclass
class RebindResult:
    """Outcome of a fuzzy rebind attempt against the live model."""

    node_id: Optional[str]
    confidence: float
    high_confidence: bool = field(init=False)
    low_confidence: bool = field(init=False)

    def __post_init__(self) -> None:
        self.high_confidence = self.confidence >= REBIND_HIGH_CONFIDENCE
        self.low_confidence = REBIND_LOW_CONFIDENCE <= self.confidence < REBIND_HIGH_CONFIDENCE


def rebind(
    anchor: AnchorFingerprint,
    candidates: list[tuple[str, str]],
) -> RebindResult:
    """Fuzzily re-resolve ``anchor`` against ``candidates``.

    Args:
        anchor: The stored fingerprint of the node we lost.
        candidates: ``(node_id, current_text)`` pairs from the live model.

    Returns:
        A :class:`RebindResult`. ``high_confidence`` results are trustworthy;
        ``low_confidence`` results must be surfaced to the user, never silently
        applied; below :data:`REBIND_LOW_CONFIDENCE` the ``node_id`` is ``None``.
    """
    best_id: Optional[str] = None
    best_score = 0.0
    target = anchor.normalized_text_fp
    for node_id, text in candidates:
        score = SequenceMatcher(None, target, normalize_text(text)).ratio()
        if score > best_score:
            best_score = score
            best_id = node_id
    if best_score < REBIND_LOW_CONFIDENCE:
        return RebindResult(node_id=None, confidence=best_score)
    return RebindResult(node_id=best_id, confidence=best_score)
