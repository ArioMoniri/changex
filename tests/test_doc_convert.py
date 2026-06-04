"""Tests for the legacy ``.doc`` -> ``.docx`` LibreOffice converter.

These stay honest and non-flaky:

* ``find_soffice`` is asserted to return a ``str`` path or ``None`` (never
  raising), independent of whether LibreOffice is installed on the runner;
* the *missing-soffice* failure path is exercised deterministically by
  monkeypatching ``find_soffice`` to ``None`` — no LibreOffice needed — and the
  error is asserted to be clear and to carry the install hint;
* path-boundary rejections (missing file, bad suffix) are asserted with no
  subprocess involved;
* the *real* conversion is only attempted when ``soffice`` is genuinely present
  AND a real ``.doc`` fixture exists; otherwise it is skipped. We do not fabricate
  a binary ``.doc`` (LibreOffice would reject it), so this never produces a flaky
  result.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from changex_core.adapters import doc_convert
from changex_core.paths import UnsafePathError


def test_find_soffice_returns_path_or_none() -> None:
    """``find_soffice`` returns an existing executable path, or ``None``."""
    result = doc_convert.find_soffice()
    assert result is None or isinstance(result, str)
    if result is not None:
        assert Path(result).exists(), f"reported soffice path does not exist: {result}"


def test_convert_raises_clear_error_when_soffice_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing LibreOffice yields an actionable error with the install hint."""
    monkeypatch.setattr(doc_convert, "find_soffice", lambda: None)

    src = tmp_path / "legacy.doc"
    src.write_bytes(b"not a real doc, but the file exists for the path check")

    with pytest.raises(RuntimeError) as excinfo:
        doc_convert.convert_doc_to_docx(str(src))

    message = str(excinfo.value)
    assert "soffice" in message.lower()
    assert "brew install --cask libreoffice" in message


def test_convert_rejects_missing_file(tmp_path: Path) -> None:
    """A path that does not exist is rejected at the boundary, before any run."""
    missing = tmp_path / "nope.doc"
    with pytest.raises(UnsafePathError):
        doc_convert.convert_doc_to_docx(str(missing))


def test_convert_rejects_bad_suffix(tmp_path: Path) -> None:
    """A non-.doc/.docx input is rejected by the suffix guard."""
    bogus = tmp_path / "notes.txt"
    bogus.write_text("hello", encoding="utf-8")
    with pytest.raises(UnsafePathError):
        doc_convert.convert_doc_to_docx(str(bogus))


def test_convert_rejects_empty_path() -> None:
    """An empty path is rejected before any I/O."""
    with pytest.raises(UnsafePathError):
        doc_convert.convert_doc_to_docx("")


def test_real_conversion_if_possible(tmp_path: Path) -> None:
    """Round-trip a real Word file through soffice when it is actually installed.

    We have no genuine binary ``.doc`` fixture in-repo (and fabricating one would
    make LibreOffice fail), so we feed a real ``.docx`` produced by python-docx —
    the converter accepts ``.docx`` and re-emits ``.docx``, which exercises the
    full subprocess + output-detection path without depending on legacy-binary
    parsing. Skipped entirely when soffice is absent.
    """
    if doc_convert.find_soffice() is None:
        pytest.skip("LibreOffice not installed; real conversion not exercised")
    pytest.importorskip("docx", reason="python-docx required to build the fixture")

    from docx import Document  # noqa: WPS433 (local import keeps skip honest)

    src = tmp_path / "sample.docx"
    document = Document()
    document.add_paragraph("Hello from a real Word file.")
    document.save(str(src))

    out_dir = tmp_path / "converted"
    produced = doc_convert.convert_doc_to_docx(str(src), out_dir=str(out_dir))

    produced_path = Path(produced)
    assert produced_path.is_file()
    assert produced_path.suffix == ".docx"
    assert produced_path.parent == out_dir.resolve()
