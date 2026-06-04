"""Tests for ``changex quicklook`` (changex_core.quicklook)."""

from __future__ import annotations

import sys

import pytest

from changex_core import quicklook as ql


def test_non_macos_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert ql.quicklook("status") == 1


def test_unknown_action_returns_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    assert ql.quicklook("bogus") == 2


def test_status_runs_without_touching_the_system(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(ql, "_pluginkit", lambda args: "")
    monkeypatch.setattr(ql, "_installed_app", lambda: None)
    assert ql.quicklook("status") == 0
    assert "Quick Look" in capsys.readouterr().out


def test_enable_without_app_installed_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(ql, "_installed_app", lambda: None)
    assert ql.quicklook("enable") == 1
