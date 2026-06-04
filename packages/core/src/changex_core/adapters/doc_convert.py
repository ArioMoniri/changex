"""Legacy ``.doc`` (Word 97-2003) ingest via LibreOffice headless conversion.

ChangeX's revision pipeline is built on the OOXML ``.docx`` container (native
``w14:paraId``, ``w:ins``/``w:del`` runs). The binary ``.doc`` format predates
that container entirely, so it cannot be loaded directly. This module bridges the
gap by shelling out to a locally-installed LibreOffice (``soffice``) in headless
mode to convert ``.doc -> .docx``; the produced ``.docx`` is then handed to the
ordinary :class:`~changex_core.adapters.docx_adapter.DocxAdapter`.

No network I/O happens here — the only subprocess invoked is the local
``soffice`` binary. Every caller-supplied path is funnelled through
:func:`~changex_core.paths.safe_path` before any filesystem or process access, so
directory-traversal and device paths are rejected at the boundary.

Each conversion runs against a **throwaway** ``-env:UserInstallation`` profile in
a fresh temp directory. This (a) keeps concurrent conversions from fighting over a
shared LibreOffice user profile lock and (b) leaves the user's real profile
untouched. The profile is cleaned up after the run.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from changex_core.paths import safe_path

# Suffixes this converter will accept as input. ``.docx`` is allowed so the
# function is a safe no-op-ish pass-through (LibreOffice will re-emit a ``.docx``)
# and callers can route either legacy or modern Word files through one door.
_ALLOWED_INPUT_SUFFIXES: tuple[str, ...] = (".doc", ".docx")

# How long to wait for the headless conversion before giving up. A cold
# LibreOffice start plus a large document can take a while, so this is generous.
_CONVERT_TIMEOUT_SECONDS: int = 180

# Shown verbatim in errors so the operator knows exactly how to fix a missing
# LibreOffice on macOS.
_INSTALL_HINT: str = "brew install --cask libreoffice"


def find_soffice() -> str | None:
    """Locate a usable LibreOffice ``soffice`` executable, or ``None``.

    Resolution order:

    1. ``soffice`` then ``libreoffice`` on ``PATH`` (covers Homebrew's
       ``/opt/homebrew/bin/soffice`` symlink and Linux package installs);
    2. the macOS application-bundle binary under both ``/Applications`` and the
       per-user ``~/Applications`` install location.

    Returns:
        An absolute path to the executable, or ``None`` if LibreOffice is not
        installed in any of the probed locations.
    """
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found

    candidates = (
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        os.path.expanduser("~/Applications/LibreOffice.app/Contents/MacOS/soffice"),
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return None


def convert_doc_to_docx(doc_path: str, out_dir: str | None = None) -> str:
    """Convert a legacy ``.doc`` (or ``.docx``) to ``.docx`` via LibreOffice.

    The input is sanitized (must exist; suffix must be ``.doc`` or ``.docx``).
    LibreOffice is run headlessly against a unique throwaway user profile so the
    call is isolated from the user's real profile and from concurrent
    conversions::

        soffice --headless --norestore --convert-to docx \\
            -env:UserInstallation=file://<tmp-profile> \\
            --outdir <out_dir> <doc_path>

    Args:
        doc_path: Path to the source ``.doc``/``.docx`` file.
        out_dir: Directory to write the produced ``.docx`` into. Defaults to the
            source file's parent directory. Created if it does not exist.

    Returns:
        The absolute path to the produced ``.docx`` file.

    Raises:
        UnsafePathError: if ``doc_path``/``out_dir`` fail sanitization, or the
            source file does not exist / has a disallowed suffix.
        RuntimeError: if LibreOffice is not installed (the message includes the
            ``brew install --cask libreoffice`` hint), if the conversion times
            out, or if it produces no output (the message includes soffice's
            captured stderr).
    """
    source = safe_path(
        doc_path, must_exist=True, allow_suffixes=_ALLOWED_INPUT_SUFFIXES
    )

    if out_dir is None:
        out_directory = source.parent
    else:
        out_directory = safe_path(out_dir)
    out_directory.mkdir(parents=True, exist_ok=True)

    soffice = find_soffice()
    if soffice is None:
        raise RuntimeError(
            "LibreOffice ('soffice') was not found, so legacy .doc files cannot "
            "be converted. Install it and retry: "
            f"{_INSTALL_HINT}"
        )

    expected = out_directory / f"{source.stem}.docx"

    # A unique throwaway LibreOffice profile per call, in its own temp dir, so
    # concurrent conversions never collide on the profile lock and the user's
    # real profile is never touched. Cleaned up in the ``finally`` below.
    profile_dir = tempfile.mkdtemp(prefix="changex-soffice-profile-")
    try:
        user_installation = Path(profile_dir).resolve().as_uri()
        cmd = [
            soffice,
            "--headless",
            "--norestore",
            f"-env:UserInstallation={user_installation}",
            "--convert-to",
            "docx",
            "--outdir",
            str(out_directory),
            str(source),
        ]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                timeout=_CONVERT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"LibreOffice conversion of {source} timed out after "
                f"{_CONVERT_TIMEOUT_SECONDS}s."
            ) from exc

        if not expected.is_file():
            stderr = _decode(completed.stderr)
            stdout = _decode(completed.stdout)
            detail = stderr or stdout or "(no output captured from soffice)"
            raise RuntimeError(
                f"LibreOffice did not produce {expected.name!r} from {source} "
                f"(exit code {completed.returncode}). soffice output:\n{detail}"
            )

        return str(expected)
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


def _decode(stream: bytes | None) -> str:
    """Decode captured subprocess output to a stripped str (never raises)."""
    if not stream:
        return ""
    return stream.decode("utf-8", errors="replace").strip()


__all__ = ["find_soffice", "convert_doc_to_docx"]
