"""``changex connect`` — wire ChangeX into an LLM app in one command.

Adding the MCP server to each client otherwise means hand-editing a JSON config (and
knowing the right path + the absolute binary location). This module does that for the
clients that use a local **stdio** server (Claude Code, Claude Desktop, Cursor, Cline,
Gemini CLI) by merging the ``changex`` entry into the right config file (backing it up
first), and prints a copy-paste runbook for the **remote** clients (ChatGPT, claude.ai)
that need ``changex-mcp --http`` behind a URL.

Design rules:

* **Never clobber.** Existing config is parsed, the ``changex`` key is merged into
  ``mcpServers`` (everything else is preserved), and a ``.changex-bak`` copy is written
  before the file is overwritten. Invalid JSON aborts loudly rather than overwriting.
* **Absolute binary for GUI apps.** GUI clients launch with a minimal ``PATH``, so the
  written command is the absolute path from ``shutil.which("changex-mcp")`` when it is on
  PATH, falling back to ``<this-python> -m changex_mcp`` so it works from any install.
* **No network, no surprises.** The remote path only *prints* the commands + connector
  config (with a freshly minted token); it never opens a tunnel or exposes a port itself.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from changex_core import ui


class ConnectError(RuntimeError):
    """Raised when a connect target cannot be configured (bad JSON, unknown target)."""


def _mcp_command() -> tuple[str, list[str]]:
    """Return ``(command, args)`` that launches the changex MCP **stdio** server.

    Prefers the installed ``changex-mcp`` console script (absolute path, so GUI apps with
    a minimal ``PATH`` still find it); falls back to ``<this interpreter> -m changex_mcp``.
    """
    exe = shutil.which("changex-mcp")
    if exe:
        return exe, []
    return sys.executable, ["-m", "changex_mcp"]


def _server_block() -> dict[str, object]:
    """The ``mcpServers.changex`` value every stdio client config uses."""
    command, args = _mcp_command()
    return {"command": command, "args": args}


def _claude_desktop_config() -> Path:
    """Per-OS path to the Claude **Desktop app** config (separate from Claude Code)."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library/Application Support/Claude/claude_desktop_config.json"
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(home)
        return Path(base) / "Claude" / "claude_desktop_config.json"
    return home / ".config/Claude/claude_desktop_config.json"


def _merge_mcp_config(path: Path) -> str:
    """Merge ``{"mcpServers": {"changex": <block>}}`` into the JSON config at ``path``.

    Preserves every other key, backs up an existing file to ``<name>.changex-bak``, and
    creates parent dirs / the file when absent. Returns ``"added"`` or ``"updated"``.

    Raises:
        ConnectError: if the file exists but is not valid JSON (we refuse to overwrite it).
    """
    data: dict[str, object] = {}
    if path.exists():
        raw = path.read_text(encoding="utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConnectError(
                f"{path} is not valid JSON ({exc}). Fix or move it aside, then retry."
            ) from exc
        if not isinstance(parsed, dict):
            raise ConnectError(f"{path} is not a JSON object; refusing to overwrite it.")
        data = parsed
        path.with_name(path.name + ".changex-bak").write_text(raw, encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)

    servers_obj = data.get("mcpServers")
    servers: dict[str, object] = servers_obj if isinstance(servers_obj, dict) else {}
    action = "updated" if "changex" in servers else "added"
    servers["changex"] = _server_block()
    data["mcpServers"] = servers
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return action


def _connect_config_file(label: str, path: Path, *, restart: str | None = None) -> None:
    """Merge the changex stdio block into ``path`` and report what happened."""
    action = _merge_mcp_config(path)
    print(ui.ok(f"changex {action} to {label}."))
    print(ui.field("config", str(path)))
    command, args = _mcp_command()
    print(ui.field("command", command + ("" if not args else " " + " ".join(args))))
    if action == "updated":
        print(ui.field("backup", str(path.name) + ".changex-bak"))
    if restart:
        print("  " + ui.warn(restart))


def _connect_claude_code() -> None:
    """Register changex with Claude **Code** at user scope via the ``claude`` CLI."""
    command, args = _mcp_command()
    add_cmd = ["claude", "mcp", "add", "-s", "user", "changex", "--", command, *args]
    if shutil.which("claude") is None:
        print(ui.warn("the `claude` CLI isn't on PATH — run this once yourself:"))
        print(ui.cmd(" ".join(add_cmd)))
        return
    result = subprocess.run(add_cmd, capture_output=True, text=True)  # noqa: S603
    out = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        print(ui.ok("changex registered with Claude Code (user scope — every folder, no duplicates)."))
        print(ui.field("verify", "claude mcp list   → changex ✓ Connected"))
    elif "already exists" in out.lower():
        print(ui.ok("changex is already registered with Claude Code."))
    else:
        print(ui.warn("`claude mcp add` failed:") + " " + (out or "unknown error"))
        print("  run manually: " + " ".join(add_cmd))


def _connect_remote(app: str) -> None:
    """Print a copy-paste runbook for a URL-based client (ChatGPT / claude.ai)."""
    token = secrets.token_hex(32)
    tunnel = shutil.which("cloudflared") or shutil.which("ngrok")
    print(ui.ok(f"{app} connects over a URL — run the HTTP server, expose it, paste the config."))
    print()
    print("  " + ui.c("1. start the local server (it edits files on THIS machine):", "bold"))
    print(ui.field("token", token))
    print(ui.cmd(f'CHANGEX_MCP_TOKEN={token} changex-mcp --http'))
    print(ui.c("     → serves http://127.0.0.1:9000/mcp", "dim"))
    print()
    print("  " + ui.c("2. expose it over HTTPS (cloud clients can't reach localhost):", "bold"))
    if tunnel and "cloudflared" in tunnel:
        print(ui.cmd("cloudflared tunnel --url http://127.0.0.1:9000"))
    elif tunnel:
        print(ui.cmd("ngrok http 9000"))
    else:
        print(ui.cmd("cloudflared tunnel --url http://127.0.0.1:9000   # or: ngrok http 9000"))
        print(ui.c("     (install one: brew install cloudflared)", "dim"))
    print()
    print("  " + ui.c(f"3. in {app} → Settings → Connectors → add an MCP server:", "bold"))
    print(ui.field("URL", "https://<your-tunnel-host>/mcp"))
    print(ui.field("header", f"Authorization: Bearer {token}"))
    print()
    print("  " + ui.c("Custom GPT instead? run `changex-api` and import its /openapi.json as an Action.", "dim"))


def _connect_cline() -> None:
    """Cline's config path varies by editor/OS — print the block + where it goes."""
    command, args = _mcp_command()
    block = {"mcpServers": {"changex": {"command": command, "args": args}}}
    print(ui.ok("Cline — add this to your Cline MCP settings (MCP Servers → Configure):"))
    print()
    print(json.dumps(block, indent=2))


@dataclass(frozen=True)
class _Target:
    summary: str
    run: Callable[[], None]


def _targets() -> dict[str, _Target]:
    return {
        "claude-code": _Target("Claude Code (terminal/IDE) — registers at user scope", _connect_claude_code),
        "claude-desktop": _Target(
            "Claude Desktop app — writes its config (restart the app after)",
            lambda: _connect_config_file(
                "Claude Desktop", _claude_desktop_config(),
                restart="fully quit & reopen Claude Desktop (⌘Q) to load it.",
            ),
        ),
        "cursor": _Target(
            "Cursor — writes ~/.cursor/mcp.json",
            lambda: _connect_config_file("Cursor", Path.home() / ".cursor/mcp.json"),
        ),
        "cline": _Target("Cline — prints the config block to paste", _connect_cline),
        "gemini": _Target(
            "Gemini CLI — writes ~/.gemini/settings.json",
            lambda: _connect_config_file("Gemini CLI", Path.home() / ".gemini/settings.json"),
        ),
        "chatgpt": _Target("ChatGPT (desktop/web) — prints the remote-connector runbook", lambda: _connect_remote("ChatGPT")),
        "claude-web": _Target("claude.ai (web) — prints the remote-connector runbook", lambda: _connect_remote("claude.ai")),
    }


def _print_menu() -> None:
    print(ui.banner("connect ChangeX to your app"))
    print("  " + ui.c("changex connect <app>", "bold") + ui.c("   — pick one:", "dim") + "\n")
    for name, target in _targets().items():
        print("    " + ui.c(name.ljust(15), "cyan") + " " + target.summary)
    print()
    print(ui.c("  Full per-app detail: docs/CALL-FROM-YOUR-APP.md", "dim"))


def connect(target: str | None) -> int:
    """Dispatch ``changex connect <target>`` (or print the menu when target is None)."""
    if not target:
        _print_menu()
        return 0
    targets = _targets()
    chosen = targets.get(target.lower())
    if chosen is None:
        print(ui.warn(f"unknown target {target!r}.") + " Choose one of: " + ", ".join(targets))
        return 2
    try:
        chosen.run()
    except ConnectError as exc:
        print(ui.warn(str(exc)))
        return 1
    return 0


def target_names() -> list[str]:
    """Public list of valid connect targets (used by the CLI parser ``choices``)."""
    return list(_targets())
