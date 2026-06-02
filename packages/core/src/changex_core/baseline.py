"""Baseline snapshot + out-of-band mismatch WARNING (degraded passive mode).

The MVP does **not** reconstruct an op stream from before/after snapshots — that
is a multi-month alignment problem that, crucially, cannot recover *which model /
turn / prompt* caused each edit. So passive mode degrades to exactly one honest
signal: a ``baseline_sha256`` mismatch warning ("document changed outside
ChangeX; N edits not attributed"). No fabricated fine-grained ops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from changex_core.journal.canonical import sha256_hex
from changex_core.paths import safe_path


@dataclass
class Baseline:
    """An immutable snapshot of a document at open time."""

    sha256: str
    uri: str
    size: int


@dataclass
class OutOfBandWarning:
    """Emitted when the document changed outside ChangeX since open."""

    expected_sha256: str
    actual_sha256: str
    message: str


def snapshot(path: str) -> Baseline:
    """Capture a baseline snapshot (sha256 + uri + size) of ``path``."""
    resolved = safe_path(path, must_exist=True)
    data = resolved.read_bytes()
    return Baseline(sha256=sha256_hex(data), uri=str(resolved), size=len(data))


def check_out_of_band(current_path: str, baseline: Baseline) -> Optional[OutOfBandWarning]:
    """Return a warning if ``current_path`` no longer matches the baseline hash.

    Returns ``None`` when the document is unchanged. The warning is deliberately
    coarse: ChangeX in the MVP cannot attribute out-of-band edits, so it reports
    that they happened rather than fabricating ops for them.
    """
    resolved = safe_path(current_path, must_exist=True)
    actual = sha256_hex(resolved.read_bytes())
    if actual == baseline.sha256:
        return None
    return OutOfBandWarning(
        expected_sha256=baseline.sha256,
        actual_sha256=actual,
        message=(
            "document changed outside ChangeX; those edits are not attributed "
            "(passive op reconstruction is out of MVP scope)"
        ),
    )


def hash_file(path: str) -> str:
    """Convenience: return the sha256 hex of a file's bytes."""
    resolved = safe_path(path, must_exist=True)
    return sha256_hex(resolved.read_bytes())
