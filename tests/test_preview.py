"""Tests for ``changex preview`` — cross-platform HTML preview (journal redline + code)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from changex_core.preview import preview_html


def _real_journal(tmp_path: Path) -> Path:
    """Build a schema-valid, hash-chained .changex via the real `track` flow."""
    docx = pytest.importorskip("docx")
    from docx.oxml.ns import qn

    base = tmp_path / "base.docx"
    doc = docx.Document()
    p = doc.add_paragraph("The quick brown fox.")
    p._p.set(qn("w14:paraId"), "20000001")
    doc.save(str(base))

    import changex_core as cx
    from changex_core.cli import main

    adapter = cx.DocxAdapter.load(str(base))
    node = next(x for x in adapter.to_model().child_paragraphs() if "quick" in x.text())
    ops = [{"kind": "text.replace", "node_id": node.node_id, "before": "quick", "after": "swift"}]
    ops_path = tmp_path / "ops.json"
    ops_path.write_text(json.dumps(ops), encoding="utf-8")

    journal = tmp_path / "x.changex"
    tracked = tmp_path / "tracked.docx"
    rc = main(["track", str(base), str(ops_path), "--out", str(tracked), "--changex", str(journal)])
    assert rc == 0
    return journal


def test_preview_changex_renders_redline(tmp_path: Path) -> None:
    html = preview_html(_real_journal(tmp_path))
    assert "<!doctype html" in html.lower()
    assert "swift" in html and "quick" in html  # insertion + deletion
    assert "<ins" in html or "<del" in html


def test_preview_code_is_solid_and_contains_source(tmp_path: Path) -> None:
    f = tmp_path / "sample.py"
    f.write_text("import math\n\ndef f(x):\n    return x * 2\n", encoding="utf-8")
    html = preview_html(f)
    assert "background:#ffffff" in html  # solid background — never blank
    assert "def" in html and "math" in html


def test_preview_code_is_highlighted_when_pygments_present(tmp_path: Path) -> None:
    pytest.importorskip("pygments")
    f = tmp_path / "sample.py"
    f.write_text("import math\n", encoding="utf-8")
    html = preview_html(f)
    # Pygments emits a .highlight container and token <span> classes.
    assert 'class="highlight"' in html
    assert "<span" in html


def test_preview_plain_fallback_without_pygments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def no_pygments(name: str, *args: object, **kwargs: object) -> object:
        if name == "pygments" or name.startswith("pygments."):
            raise ImportError("pygments disabled for test")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", no_pygments)
    f = tmp_path / "x.txt"
    f.write_text("plain <text> & more\n", encoding="utf-8")
    html = preview_html(f)
    assert "<pre>" in html
    assert "&lt;text&gt;" in html  # escaped, not raw


def test_preview_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        preview_html(tmp_path / "nope.py")
