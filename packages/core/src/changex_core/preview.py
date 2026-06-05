"""``changex preview`` — render ANY file to a self-contained HTML preview.

Cross-platform (macOS, Windows, Linux). Two modes, chosen by the file:

* a ``.changex`` journal → the tracked-change redline (the same view the macOS Quick
  Look extension and ``changex review`` produce);
* any other file → its source, syntax-highlighted with Pygments when available, else a
  plain (escaped) ``<pre>`` block.

This is the engine the **Windows preview handler** wraps (it shells out to
``changex preview <file>`` and shows the HTML in a WebView2), so Windows gets the same
preview as macOS Quick Look without re-implementing the renderer.
"""

from __future__ import annotations

from pathlib import Path

from changex_core.journal.journal import Journal
from changex_core.paths import safe_path
from changex_core.render.html import render_html

#: Extensions we treat as a ChangeX journal rather than source code.
_JOURNAL_SUFFIXES = (".changex", ".jsonl")


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _looks_like_journal(path: Path) -> bool:
    if path.suffix.lower() in _JOURNAL_SUFFIXES:
        return True
    try:
        with path.open("r", encoding="utf-8") as fh:
            head = fh.readline(400)
    except (OSError, UnicodeDecodeError):
        return False
    return '"type": "header"' in head or '"op_schema_version"' in head


def _page(extra_head: str, body: str, *, title: str) -> str:
    """Self-contained HTML with a SOLID background (never blank) for a code/text file."""
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='color-scheme' content='light'>"
        f"<title>{_esc(title)}</title><style>"
        "html,body{margin:0;background:#ffffff;color:#1d1d1f}"
        "body{font:13px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}"
        "pre{margin:0;padding:14px 16px;overflow:auto;"
        "font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;line-height:1.5;tab-size:4}"
        ".highlight{background:#ffffff}"
        f"{extra_head}</style></head><body>{body}</body></html>"
    )


def _code_html(path: Path, title: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        text = path.read_bytes().decode("utf-8", errors="replace")

    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import TextLexer, guess_lexer_for_filename
        from pygments.util import ClassNotFound

        try:
            lexer = guess_lexer_for_filename(path.name, text)
        except ClassNotFound:
            lexer = TextLexer()
        formatter = HtmlFormatter(style="default")
        body = highlight(text, lexer, formatter)
        css = formatter.get_style_defs(".highlight")
        return _page(css, body, title=title)
    except ImportError:
        # No Pygments — still readable, just uncoloured. (`pip install changex-core[preview]`)
        return _page("", f"<pre>{_esc(text)}</pre>", title=title)


def preview_html(path: str | Path) -> str:
    """Return a self-contained HTML preview for ``path`` (journal redline or code)."""
    p = safe_path(str(path), must_exist=True)
    if _looks_like_journal(p):
        journal = Journal.open(str(p))
        return render_html(journal.active_events(), title=p.name)
    return _code_html(p, title=p.name)
