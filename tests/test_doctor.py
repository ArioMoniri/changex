"""Tests for ``changex doctor`` (changex_core.doctor)."""

from __future__ import annotations

from pathlib import Path

import pytest

from changex_core.doctor import _probe, controlling_app, doctor


def test_probe_ok_on_readable_file(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("hi")
    assert _probe(p) == "ok"


def test_probe_ok_on_dir(tmp_path: Path) -> None:
    assert _probe(tmp_path) == "ok"


def test_probe_missing(tmp_path: Path) -> None:
    assert _probe(tmp_path / "does-not-exist.txt") == "missing"


def test_controlling_app_shape() -> None:
    r = controlling_app()
    assert r is None or (isinstance(r, tuple) and len(r) == 2 and all(isinstance(x, str) for x in r))


def test_doctor_returns_int_and_prints(capsys: pytest.CaptureFixture[str]) -> None:
    rc = doctor()
    assert rc in (0, 1)
    out = capsys.readouterr().out
    assert "Install" in out
