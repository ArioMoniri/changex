"""``changex doctor`` — diagnose the install and macOS file-access (TCC) problems.

The #1 reason "changex can't open my file" is **macOS privacy (TCC)**: the OS denies the
*controlling app* (Claude.app, Terminal, iTerm, VS Code, Cursor, …) access to the protected
folders ``~/Downloads`` / ``~/Documents`` / ``~/Desktop``. A child process inherits its
parent's TCC grants, so the ``changex-mcp`` server a host app launches is blocked exactly
when that host app is — and the file simply can't be read. No app can grant itself this
(it's an OS rule), so this command:

* names the **controlling app** that needs the grant (walks the process tree),
* probes which folders are actually blocked,
* prints the one-time **Full Disk Access** fix (with a deep link to the right pane), and
* offers the **zero-permission** alternatives: upload the doc to Claude, or open it through
  the app's file picker (a picker selection *is* the grant).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from changex_core import ui

FDA_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
_PROTECTED = ("Downloads", "Documents", "Desktop")


def _probe(path: Path) -> str:
    """Return 'ok' / 'blocked' (TCC) / 'missing' for read access to ``path``."""
    try:
        if path.is_dir():
            next(os.scandir(path), None)
        else:
            with open(path, "rb") as fh:
                fh.read(1)
        return "ok"
    except PermissionError:
        return "blocked"
    except FileNotFoundError:
        return "missing"
    except OSError as exc:
        return "blocked" if exc.errno == 1 else f"error:{exc.errno}"


def _ancestry() -> list[str]:
    """The executable path of each ancestor process, nearest first (macOS/Unix)."""
    chain: list[str] = []
    pid = os.getpid()
    for _ in range(24):
        try:
            res = subprocess.run(
                ["ps", "-o", "ppid=,comm=", "-p", str(pid)],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            break
        line = res.stdout.strip()
        if not line:
            break
        head, _, comm = line.partition(" ")
        comm = comm.strip()
        if comm:
            chain.append(comm)
        try:
            ppid = int(head)
        except ValueError:
            break
        if ppid <= 1:
            break
        pid = ppid
    return chain


def controlling_app() -> tuple[str, str] | None:
    """Best-effort: the .app (or terminal/IDE) whose TCC grant governs file access.

    Returns ``(display_name, path_or_name)`` or ``None``. The topmost ``*.app`` in the
    process ancestry is the one that must be granted Full Disk Access.
    """
    marker = ".app/Contents/MacOS/"
    app: str | None = None
    for comm in _ancestry():
        if marker in comm:
            app = comm.split(marker)[0] + ".app"  # keep updating → topmost wins
    if app:
        return (Path(app).stem, app)
    known = {"Terminal": "Terminal", "iTerm2": "iTerm", "Code": "VS Code", "Cursor": "Cursor"}
    for comm in _ancestry():
        name = Path(comm).name
        if name in known:
            return (known[name], name)
    return None


def _ver(pkg: str) -> str:
    try:
        return version(pkg)
    except PackageNotFoundError:
        return "—"


def doctor(open_settings: bool = False) -> int:
    """Print an install + file-access diagnosis. Returns 0 (ok) or 1 (issues)."""
    ui.print_banner("doctor — install & file-access check")
    issues = 0

    # 1) install
    print("  " + ui.c("Install", "bold", "magenta"))
    print(ui.field("changex-core", _ver("changex-core")))
    for b in ("changex", "changex-mcp", "changex-api"):
        print(ui.field(b, shutil.which(b) or ui.c("not on PATH", "yellow")))
    print()

    macos = sys.platform == "darwin"
    if not macos:
        print("  " + ui.c("(file-access checks are macOS-specific; nothing to diagnose here)", "dim"))
        return 0

    # 2) controlling app
    app = controlling_app()
    print("  " + ui.c("Controlling app", "bold", "magenta") + ui.c("  (its macOS permission governs file access)", "dim"))
    if app:
        print(ui.field("app", f"{app[0]}  ({app[1]})"))
    else:
        print(ui.field("app", "unknown"))
    print()

    # 3) access probes
    print("  " + ui.c("File access", "bold", "magenta"))
    home = Path.home()
    blocked: list[str] = []

    def _row(label: str, state: str) -> None:
        tone = "good" if state == "ok" else ("bad" if state == "blocked" else "yellow")
        print("    " + ui.c(label.ljust(14), "cyan") + ui.c(state, tone))
        if state == "blocked":
            blocked.append(label)

    _row("home (~)", _probe(home))
    try:  # the cwd itself can be access-denied (e.g. running from inside ~/Downloads)
        _row("current dir", _probe(Path.cwd()))
    except OSError:
        _row("current dir", "blocked")
    for name in _PROTECTED:
        _row(f"~/{name}", _probe(home / name))
    print()

    # 4) verdict + fix
    if blocked:
        issues = 1
        who = app[0] if app else "the app running changex"
        print("  " + ui.warn(f"{who} is blocked from: {', '.join(blocked)} (macOS privacy / TCC)."))
        print("  " + ui.c("Fix it once — grant Full Disk Access:", "bold"))
        print("    1. Quit " + ui.c(who, "bold") + " completely (⌘Q).")
        print("    2. System Settings → Privacy & Security → " + ui.c("Full Disk Access", "bold"))
        print("       " + ui.c("open it directly: ", "dim") + ui.c(f"open '{FDA_URL}'", "cyan"))
        print(f"    3. Turn ON {ui.c(who, 'bold')} (add it with ➕ if missing), then reopen it.")
        print()
        print("  " + ui.c("…or skip permissions entirely:", "bold"))
        print("    • In Claude Desktop, " + ui.c("upload the document into the chat", "bold")
              + " and ask changex to edit it — the upload lands where changex can read it.")
        print("    • Or move the file out of Downloads/Documents/Desktop (e.g. to your home folder).")
        if open_settings:
            subprocess.run(["open", FDA_URL], check=False)
            print()
            print("  " + ui.ok("opened the Full Disk Access settings pane."))
    else:
        print("  " + ui.ok("file access looks good — changex can read your documents. ✓"))
    return issues
