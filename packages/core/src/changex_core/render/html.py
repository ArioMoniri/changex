"""HTML / markdown redline projection of the journal.

This is the MVP review surface that sits alongside the native tracked ``.docx``
(Word renders the real accept/reject). It reads the journal events and renders an
inline redline with a per-op provenance tooltip, so a reviewer can answer "what
changed, where, why, by whom" without opening Word.

No network access; pure string assembly. Both an HTML and a markdown projection
are provided from the same event walk.
"""

from __future__ import annotations

import html
from typing import Iterable

from changex_core.journal.events import Event

_CSS = """
body { font: 14px/1.5 -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; }
h1 { font-size: 1.4rem; }
.op { padding: .4rem .6rem; border-left: 3px solid #ddd; margin: .3rem 0; }
ins { background: #e6ffed; text-decoration: none; }
del { background: #ffeef0; }
.meta { color: #666; font-size: .8rem; }
.reverted { opacity: .45; }
.kind { font-weight: 600; }
""".strip()


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _op_summary_html(event: Event) -> str:
    op = event.op
    kind = op.get("kind", "?")
    if kind == "text.insert":
        body = f"<ins>{_esc(op.get('text'))}</ins>"
        if op.get("before_anchor"):
            body = f"after &ldquo;{_esc(op['before_anchor'])}&rdquo;: " + body
    elif kind == "text.delete":
        body = f"<del>{_esc(op.get('before'))}</del>"
    elif kind == "text.replace":
        body = f"<del>{_esc(op.get('before'))}</del> <ins>{_esc(op.get('after'))}</ins>"
    elif kind == "style.change":
        body = f"style {_esc(op.get('before'))} &rarr; <ins>{_esc(op.get('style'))}</ins>"
    elif kind == "node.insert":
        body = f"<ins>+ {_esc(op.get('value', {}).get('text', ''))}</ins>"
    elif kind == "node.delete":
        body = f"<del>&minus; {_esc(op.get('value', {}).get('text', ''))}</del>"
    else:  # pragma: no cover - frozen set
        body = _esc(op)
    return body


def _provenance_line(event: Event) -> str:
    p = event.provenance
    bits = [f"seq {event.seq}", _esc(event.target.node_id)]
    if p.agent:
        bits.append(_esc(p.agent))
    if p.vendor:
        bits.append(_esc(p.vendor))
    bits.append(_esc(p.provenance_source))
    if p.rationale:
        bits.append(f"&ldquo;{_esc(p.rationale)}&rdquo;")
    bits.append(_esc(p.ts))
    return " &middot; ".join(bits)


def render_html(events: Iterable[Event], *, title: str = "ChangeX review") -> str:
    """Render an inline HTML redline of ``events`` with provenance tooltips."""
    rows: list[str] = []
    for event in events:
        cls = "op"
        rows.append(
            f'<div class="{cls}">'
            f'<span class="kind">{_esc(event.op.get("kind"))}</span> '
            f"{_op_summary_html(event)}"
            f'<div class="meta">{_provenance_line(event)}</div>'
            f"</div>"
        )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body>"
        f"<h1>{_esc(title)}</h1>"
        + "".join(rows)
        + "</body></html>"
    )


def render_markdown(events: Iterable[Event], *, title: str = "ChangeX review") -> str:
    """Render a markdown redline of ``events`` (for CLI / plain-text review)."""
    lines = [f"# {title}", ""]
    for event in events:
        op = event.op
        kind = op.get("kind", "?")
        if kind == "text.insert":
            change = f"**+** `{op.get('text')}`"
        elif kind == "text.delete":
            change = f"**~~{op.get('before')}~~**"
        elif kind == "text.replace":
            change = f"~~{op.get('before')}~~ -> `{op.get('after')}`"
        elif kind == "style.change":
            change = f"style {op.get('before')} -> {op.get('style')}"
        elif kind == "node.insert":
            change = f"**+ para** `{op.get('value', {}).get('text', '')}`"
        elif kind == "node.delete":
            change = f"**- para** ~~{op.get('value', {}).get('text', '')}~~"
        else:  # pragma: no cover
            change = str(op)
        prov = event.provenance
        who = prov.agent or "unknown"
        lines.append(
            f"- `seq {event.seq}` **{kind}** @ `{event.target.node_id}` — "
            f"{change} _({who}, {prov.provenance_source})_"
        )
    lines.append("")
    return "\n".join(lines)
