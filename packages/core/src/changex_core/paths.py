"""Filesystem path sanitization for every system boundary.

All public entry points (adapters, journal, CLI) funnel caller-supplied paths
through :func:`safe_path` so directory-traversal and accidental device paths are
rejected before any I/O happens. There are **no network calls** anywhere in this
package; only local files are touched.
"""

from __future__ import annotations

import os
from pathlib import Path


class UnsafePathError(ValueError):
    """Raised when a caller-supplied path fails sanitization."""


def safe_path(
    candidate: str | os.PathLike[str],
    *,
    must_exist: bool = False,
    allow_suffixes: tuple[str, ...] | None = None,
    base_dir: str | os.PathLike[str] | None = None,
) -> Path:
    """Normalize and validate ``candidate`` into an absolute :class:`Path`.

    Args:
        candidate: The caller-supplied path.
        must_exist: If ``True``, the resolved file must already exist.
        allow_suffixes: If given, the path's suffix (lowercased) must be one of
            these (e.g. ``(".docx",)``).
        base_dir: If given, the resolved path must live under this directory —
            this is the directory-traversal guard for confined workspaces.

    Returns:
        The resolved absolute path.

    Raises:
        UnsafePathError: on empty input, a NUL byte, a disallowed suffix, escape
            outside ``base_dir``, or (when ``must_exist``) a missing file.
    """
    if candidate is None or str(candidate).strip() == "":
        raise UnsafePathError("path must be a non-empty string")
    raw = os.fspath(candidate)
    if "\x00" in raw:
        raise UnsafePathError("path contains a NUL byte")

    resolved = Path(raw).expanduser().resolve()

    if allow_suffixes is not None:
        suffix = resolved.suffix.lower()
        if suffix not in allow_suffixes:
            raise UnsafePathError(
                f"path suffix {suffix!r} not in allowed {allow_suffixes!r}"
            )

    if base_dir is not None:
        base = Path(os.fspath(base_dir)).expanduser().resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise UnsafePathError(
                f"path {resolved} escapes confined base {base}"
            ) from exc

    if must_exist and not resolved.exists():
        raise UnsafePathError(f"path does not exist: {resolved}")

    return resolved
