"""``changex quicklook`` — manage the macOS Quick Look preview for ``.changex`` files.

The preview itself is a native macOS app-extension shipped in the **ChangeX Quick Look**
helper app (built from ``packages/quicklook``; downloadable from the releases page). This
CLI is the headless controller for it — check status, enable/disable the extension via
``pluginkit``, and open the relevant settings — so it works the same from the terminal as
the in-app buttons do.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from changex_core import ui

EXT_ID = "dev.changex.ChangeXQuickLook.QuickLookExtension"
_APP_PATHS = (
    Path("/Applications/ChangeXQuickLook.app"),
    Path.home() / "Applications/ChangeXQuickLook.app",
)
_RELEASES = "https://github.com/ArioMoniri/changex/releases/latest"


def _macos() -> bool:
    return sys.platform == "darwin"


def _pluginkit(args: list[str]) -> str:
    try:
        res = subprocess.run(
            ["pluginkit", *args], capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return (res.stdout + res.stderr).strip()


def _installed_app() -> Path | None:
    return next((p for p in _APP_PATHS if p.exists()), None)


def _is_enabled() -> bool | None:
    out = _pluginkit(["-m", "-i", EXT_ID])
    if not out:
        return None
    return out.startswith("+")


def _status() -> int:
    print("  " + ui.c("ChangeX Quick Look", "bold", "magenta"))
    app = _installed_app()
    print(ui.field("helper app", str(app) if app else ui.c("not installed", "yellow")))
    enabled = _is_enabled()
    state = (
        ui.c("not registered", "yellow")
        if enabled is None
        else (ui.c("enabled ✓", "green") if enabled else ui.c("disabled", "yellow"))
    )
    print(ui.field("preview", state))
    if app is None:
        print()
        print("  Install the helper app (one download), then `changex quicklook enable`:")
        print(ui.cmd(f"open {_RELEASES}   # grab ChangeX-QuickLook.dmg"))
    elif enabled is None:
        print()
        print("  " + ui.c("Open the app once so macOS registers the extension:", "dim"))
        print(ui.cmd(f"open '{app}'"))
    return 0


def quicklook(action: str | None) -> int:
    """Dispatch ``changex quicklook [status|enable|disable|open]``."""
    if not _macos():
        print(ui.warn("Quick Look previews are macOS-only."))
        return 1
    action = (action or "status").lower()
    if action == "status":
        return _status()
    if action in ("enable", "disable"):
        if _installed_app() is None:
            print(ui.warn("ChangeX Quick Look helper app isn't installed yet."))
            print("  Get it: " + ui.cmd(f"open {_RELEASES}"))
            return 1
        _pluginkit(["-e", "use" if action == "enable" else "ignore", "-i", EXT_ID])
        verb = "enabled" if action == "enable" else "disabled"
        print(ui.ok(f"Quick Look preview {verb}."))
        return 0
    if action == "open":
        app = _installed_app()
        if app:
            subprocess.run(["open", str(app)], check=False)
        else:
            subprocess.run(["open", _RELEASES], check=False)
        return 0
    print(ui.warn(f"unknown action {action!r}; use: status | enable | disable | open"))
    return 2
