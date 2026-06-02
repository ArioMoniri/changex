"""Append-only ``.changex`` journal: JCS hash chain, replay, verify, revert."""

from __future__ import annotations

from changex_core.journal.canonical import canonicalize, chain_hash, sha256_hex
from changex_core.journal.events import (
    CHANGEX_VERSION,
    Event,
    Header,
    Provenance,
    Target,
    new_id,
    utc_now_iso,
)
from changex_core.journal.journal import Journal, JournalError, VerifyResult

__all__ = [
    "Journal",
    "JournalError",
    "VerifyResult",
    "Event",
    "Header",
    "Provenance",
    "Target",
    "new_id",
    "utc_now_iso",
    "CHANGEX_VERSION",
    "canonicalize",
    "chain_hash",
    "sha256_hex",
]
