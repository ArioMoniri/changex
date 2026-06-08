"""Tests for ``changex connect`` config merging (changex_core.connect)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from changex_core.connect import (
    ConnectError,
    _merge_mcp_config,
    _server_block,
    connect,
    target_names,
)


def test_server_block_shape() -> None:
    block = _server_block()
    assert "command" in block and "args" in block
    assert isinstance(block["args"], list)


def test_merge_creates_file_when_absent(tmp_path: Path) -> None:
    cfg = tmp_path / "nested" / "mcp.json"
    action = _merge_mcp_config(cfg)
    assert action == "added"
    data = json.loads(cfg.read_text())
    assert "changex" in data["mcpServers"]
    assert data["mcpServers"]["changex"]["command"]  # non-empty command


def test_merge_preserves_existing_servers_and_backs_up(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "keepme": 1}))
    action = _merge_mcp_config(cfg)
    assert action == "added"
    data = json.loads(cfg.read_text())
    # other servers + unrelated keys preserved, changex added
    assert set(data["mcpServers"]) == {"other", "changex"}
    assert data["keepme"] == 1
    # a backup of the original was written
    assert (tmp_path / "claude_desktop_config.json.changex-bak").exists()


def test_merge_reports_updated_when_changex_present(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"changex": {"command": "old"}}}))
    assert _merge_mcp_config(cfg) == "updated"


def test_merge_is_idempotent_no_rewrite_when_unchanged(tmp_path: Path) -> None:
    # Safe for the Viewer to run on every launch: a second identical merge is a no-op
    # (returns "unchanged" and does not write a fresh backup).
    cfg = tmp_path / "claude_desktop_config.json"
    assert _merge_mcp_config(cfg) == "added"
    bak = tmp_path / "claude_desktop_config.json.changex-bak"
    assert not bak.exists()  # nothing to back up on first create
    assert _merge_mcp_config(cfg) == "unchanged"
    assert not bak.exists()  # unchanged → no rewrite, no backup


def test_merge_refuses_invalid_json(tmp_path: Path) -> None:
    cfg = tmp_path / "broken.json"
    cfg.write_text("{ not json ")
    with pytest.raises(ConnectError):
        _merge_mcp_config(cfg)
    # the broken file is left untouched (not overwritten)
    assert cfg.read_text() == "{ not json "


def test_merge_refuses_non_object_json(tmp_path: Path) -> None:
    cfg = tmp_path / "list.json"
    cfg.write_text("[1, 2, 3]")
    with pytest.raises(ConnectError):
        _merge_mcp_config(cfg)


def test_connect_unknown_target_returns_2() -> None:
    assert connect("definitely-not-an-app") == 2


def test_connect_menu_returns_0() -> None:
    assert connect(None) == 0


def test_target_names_cover_core_apps() -> None:
    names = target_names()
    for expected in ("claude-code", "claude-desktop", "chatgpt", "cursor", "gemini"):
        assert expected in names


def test_connect_all_connects_detected_local_apps(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    """`changex connect all` (connect_all) writes the config of each detected local app."""
    import json

    from changex_core import connect as C

    cfg = tmp_path / "claude_desktop_config.json"
    monkeypatch.setattr(C, "_claude_desktop_config", lambda: cfg)
    monkeypatch.setattr(C, "_claude_desktop_installed", lambda: True)
    monkeypatch.setattr(C.shutil, "which", lambda name: None)   # no claude CLI
    monkeypatch.setattr(C.Path, "home", lambda: tmp_path)        # no ~/.cursor or ~/.gemini

    C.connect_all()

    assert "changex" in json.loads(cfg.read_text())["mcpServers"]
    assert "Connected: Claude Desktop" in capsys.readouterr().out
