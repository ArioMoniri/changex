"""Tiny terminal-UI helpers: an ASCII banner + ANSI niceties (NO_COLOR-aware).

Color is only emitted to a TTY and is suppressed by ``NO_COLOR`` or
``CHANGEX_NO_COLOR``, so piped/redirected output stays clean.
"""

from __future__ import annotations

import os
import sys

_ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}

_LOGO = r"""
 ╔═╗╦ ╦╔═╗╔╗╔╔═╗╔═╗═╗ ╦
 ║  ╠═╣╠═╣║║║║ ╦║╣ ╔╩╦╝
 ╚═╝╩ ╩╩ ╩╝╚╝╚═╝╚═╝╩ ╚═
"""


def _use_color(stream=None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") or os.environ.get("CHANGEX_NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def c(text: str, *styles: str, stream=None) -> str:
    """Wrap ``text`` in ANSI styles when the stream is an interactive TTY."""
    if not styles or not _use_color(stream):
        return text
    prefix = "".join(_ANSI.get(s, "") for s in styles)
    return f"{prefix}{text}{_ANSI['reset']}"


def banner(subtitle: str = "provenance-first change tracking for AI document edits") -> str:
    """Return the ChangeX ASCII banner with a subtitle."""
    logo = "\n".join(c(line, "cyan", "bold") for line in _LOGO.strip("\n").splitlines())
    return f"{logo}\n {c(subtitle, 'dim')}\n"


def print_banner(subtitle: str | None = None, *, stream=None) -> None:
    stream = stream or sys.stdout
    print(banner(subtitle) if subtitle is not None else banner(), file=stream)


def ok(msg: str) -> str:
    return c("✓ ", "green", "bold") + msg


def warn(msg: str) -> str:
    return c("! ", "yellow", "bold") + msg


def cmd(line: str) -> str:
    """Format a runnable command line (cyan)."""
    return "    " + c(line, "cyan")


def field(label: str, value: object) -> str:
    return f"  {label:<14}: {value}"
