"""Tiny terminal-UI helpers: an ASCII banner + ANSI niceties (NO_COLOR-aware).

Color is only emitted to a TTY and is suppressed by ``NO_COLOR`` or
``CHANGEX_NO_COLOR``, so piped/redirected output stays clean.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import TextIO

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

# Large banner (wide terminals). Small box-drawing fallback for narrow terminals.
_LOGO_BIG = r"""
 ██████╗██╗  ██╗ █████╗ ███╗   ██╗ ██████╗ ███████╗██╗  ██╗
██╔════╝██║  ██║██╔══██╗████╗  ██║██╔════╝ ██╔════╝╚██╗██╔╝
██║     ███████║███████║██╔██╗ ██║██║  ███╗█████╗   ╚███╔╝
██║     ██╔══██║██╔══██║██║╚██╗██║██║   ██║██╔══╝   ██╔██╗
╚██████╗██║  ██║██║  ██║██║ ╚████║╚██████╔╝███████╗██╔╝ ██╗
 ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
"""

_LOGO_SMALL = r"""
 ╔═╗╦ ╦╔═╗╔╗╔╔═╗╔═╗═╗ ╦
 ║  ╠═╣╠═╣║║║║ ╦║╣ ╔╩╦╝
 ╚═╝╩ ╩╩ ╩╝╚╝╚═╝╚═╝╩ ╚═
"""

# 256-color cyan→teal vertical gradient applied to the big banner, top to bottom.
_GRADIENT = (51, 45, 44, 38, 37, 31)


def _use_color(stream: TextIO | None = None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") or os.environ.get("CHANGEX_NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def c(text: str, *styles: str, stream: TextIO | None = None) -> str:
    """Wrap ``text`` in ANSI styles when the stream is an interactive TTY."""
    if not styles or not _use_color(stream):
        return text
    prefix = "".join(_ANSI.get(s, "") for s in styles)
    return f"{prefix}{text}{_ANSI['reset']}"


def _grad(text: str, code: int) -> str:
    """Bold 256-color foreground (used for the big banner's vertical gradient)."""
    return f"\033[1;38;5;{code}m{text}{_ANSI['reset']}"


def banner(subtitle: str = "provenance-first change tracking for AI document edits") -> str:
    """Return the ChangeX banner + subtitle.

    Uses the large block logo on terminals at least 62 columns wide (with a cyan→teal
    gradient when color is on), and the compact box-drawing logo on narrow terminals.
    """
    big = shutil.get_terminal_size((80, 24)).columns >= 62
    lines = (_LOGO_BIG if big else _LOGO_SMALL).strip("\n").splitlines()
    if not _use_color():
        logo = "\n".join(lines)
    elif big:
        logo = "\n".join(_grad(line, _GRADIENT[min(i, len(_GRADIENT) - 1)]) for i, line in enumerate(lines))
    else:
        logo = "\n".join(c(line, "cyan", "bold") for line in lines)
    return f"{logo}\n {c(subtitle, 'dim')}\n"


def print_banner(subtitle: str | None = None, *, stream: TextIO | None = None) -> None:
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
