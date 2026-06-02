"""Document-outline redline: the original file's structure with changes in place.

Unlike :func:`changex_core.render.html.render_html` (an op-by-op log), this reads the
*tracked* ``.docx`` and renders the full document — headings and paragraphs in their
real order — with the AI's insertions and deletions marked **inline**, each carrying a
provenance tooltip (author/date from the revision). This is the "see the changes in the
document itself" view.

Pure string assembly + python-docx/lxml; no network access.
"""

from __future__ import annotations

import html
from typing import Iterable

from changex_core.journal.events import Event
from changex_core.paths import safe_path

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _q(tag: str) -> str:
    return f"{{{_W}}}{tag}"


_CSS = """
body { font: 15px/1.65 -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
       background: #f6f7f9; color: #1a1a1a; }
.wrap { max-width: 820px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }
h1.report { font-size: 1.1rem; color: #555; font-weight: 600; margin: 0 0 .25rem; }
.legend { color: #777; font-size: .82rem; margin: 0 0 1.25rem; }
.legend ins, .legend del { padding: 0 .2rem; }
.page { background: #fff; border: 1px solid #e3e6ea; border-radius: 8px;
        padding: 2.5rem 3rem; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.page h1 { font-size: 1.7rem; margin: 1.2rem 0 .6rem; }
.page h2 { font-size: 1.35rem; margin: 1.1rem 0 .5rem; }
.page h3 { font-size: 1.15rem; margin: 1rem 0 .4rem; }
.page h4 { font-size: 1.02rem; margin: .9rem 0 .3rem; }
.page p  { margin: .55rem 0; }
ins { background: #e6ffed; color: #04612b; text-decoration: none; border-radius: 2px; }
del { background: #ffeef0; color: #9b1c2c; text-decoration: line-through; border-radius: 2px; }
ins, del { padding: 0 .12rem; cursor: help; }
.badge { font-size: .68rem; color: #8a5a00; background: #fff4d6; border: 1px solid #f0d88a;
         border-radius: 10px; padding: .03rem .4rem; margin-left: .4rem; vertical-align: middle; }
.changelog { margin-top: 2rem; }
.changelog h2 { font-size: .95rem; color: #555; }
.changelog ol { padding-left: 1.2rem; color: #444; font-size: .86rem; }
.changelog code { background: #eef0f2; padding: 0 .25rem; border-radius: 3px; }
""".strip()


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _run_text(run_el) -> str:
    """Concatenate the text in a ``w:r`` (handles ``w:t`` / ``w:delText`` / ``w:tab``)."""
    parts: list[str] = []
    for node in run_el.iter():
        if node.tag in (_q("t"), _q("delText")):
            parts.append(node.text or "")
        elif node.tag == _q("tab"):
            parts.append("\t")
    return "".join(parts)


def _heading_tag(style_name: str | None) -> str:
    s = (style_name or "").lower()
    if s.startswith("title"):
        return "h1"
    if s.startswith("heading 1"):
        return "h2"
    if s.startswith("heading 2"):
        return "h3"
    if s.startswith("heading"):
        return "h4"
    return "p"


def _mark(child, kind: str) -> str:
    """Render a ``w:ins``/``w:del`` element as ``<ins>``/``<del>`` with a tooltip."""
    author = child.get(_q("author"))
    date = child.get(_q("date"))
    text = "".join(_run_text(r) for r in child.findall(_q("r")))
    verb = "inserted" if kind == "ins" else "deleted"
    tip = _esc(f"{verb} by {author or 'AI'}" + (f" · {date}" if date else ""))
    return f'<{kind} title="{tip}">{_esc(text)}</{kind}>'


def _changelog(events: Iterable[Event]) -> str:
    items: list[str] = []
    for e in events:
        who = e.provenance.agent or "unknown"
        why = f' &mdash; &ldquo;{_esc(e.provenance.rationale)}&rdquo;' if e.provenance.rationale else ""
        items.append(
            f"<li><code>seq {e.seq}</code> {_esc(e.op.get('kind'))} "
            f"@ <code>{_esc(e.target.node_id)}</code> "
            f"<span style='color:#888'>({_esc(who)})</span>{why}</li>"
        )
    if not items:
        return ""
    return (
        '<div class="changelog"><h2>Change log (who / why)</h2><ol>'
        + "".join(items)
        + "</ol></div>"
    )


def render_document_html(
    docx_path: str,
    *,
    title: str = "ChangeX review",
    events: Iterable[Event] | None = None,
) -> str:
    """Render a tracked ``.docx`` as its full outline with changes shown inline.

    ``events`` (optional) appends a provenance "change log" for who/why context.
    """
    from docx import Document

    path = safe_path(docx_path, must_exist=True, allow_suffixes=(".docx",))
    doc = Document(str(path))

    blocks: list[str] = []
    for para in doc.paragraphs:
        style_name = para.style.name if para.style is not None else None
        tag = _heading_tag(style_name)
        ppr = para._p.find(_q("pPr"))
        badge = ""
        if ppr is not None and ppr.find(_q("pPrChange")) is not None:
            badge = f'<span class="badge">style &rarr; {_esc(style_name)}</span>'
        inline: list[str] = []
        for child in para._p:
            if child.tag == _q("r"):
                inline.append(_esc(_run_text(child)))
            elif child.tag == _q("ins"):
                inline.append(_mark(child, "ins"))
            elif child.tag == _q("del"):
                inline.append(_mark(child, "del"))
        content = "".join(inline)
        if not content.strip() and tag == "p" and not badge:
            content = "&nbsp;"
        blocks.append(f"<{tag}>{content}{badge}</{tag}>")

    changelog = _changelog(events) if events is not None else ""
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body><div class='wrap'>"
        f'<h1 class="report">{_esc(title)}</h1>'
        '<p class="legend">Changes shown inline in the document: '
        "<ins>insertions</ins> &middot; <del>deletions</del> &middot; "
        "hover a change for who/when.</p>"
        '<div class="page">' + "".join(blocks) + "</div>"
        + changelog
        + "</div></body></html>"
    )
