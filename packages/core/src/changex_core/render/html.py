"""HTML / markdown projection of the journal.

The HTML projection is a **GitKraken-style commit graph**: every edit in the hash-chained
journal is a "commit" — a node on a vertical graph rail, coloured by author, carrying its
short hash, the redline (deleted/inserted text), the document part it touched, the author,
and a timestamp. It is the review surface that sits alongside the native tracked ``.docx``
(Word renders the real accept/reject) and answers "what changed, where, when, why, by whom".

Pure string assembly — **no JavaScript** (the viewer renders it inside a sandboxed iframe)
and no network. The same event walk also produces a plain markdown projection.
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Iterable

from changex_core.journal.events import Event

# GitKraken-ish vibrant lane colours; an author maps deterministically to one.
_LANE_COLORS = [
    "#4dd0e1", "#ba68c8", "#ff8a65", "#f06292", "#64b5f6",
    "#81c784", "#ffd54f", "#9575cd", "#4db6ac", "#f48fb1",
]


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
    elif kind == "format.run":
        body = f"format {_esc(op.get('props'))}"
    elif kind == "node.move":
        body = f"moved {_esc(op.get('node_id'))}"
    else:  # pragma: no cover - frozen set
        body = _esc(op)
    return body


def _lane_color(name: str) -> str:
    if not name:
        return "#8b91a0"
    return _LANE_COLORS[sum(ord(c) for c in name) % len(_LANE_COLORS)]


def _initials(name: str) -> str:
    parts = [p for p in name.replace("-", " ").replace("_", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def _fmt_ts(iso: str) -> tuple[str, str]:
    """Return (human, iso) — a readable absolute timestamp + the raw value for the title."""
    if not iso:
        return "", ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y · %H:%M"), iso
    except (ValueError, TypeError):
        return iso, iso


def render_html(
    events: Iterable[Event],
    *,
    title: str = "ChangeX review",
    header: dict[str, Any] | None = None,
) -> str:
    """Render the journal as a GitKraken-style commit graph (self-contained HTML)."""
    evs = list(events)

    authors: dict[str, int] = {}
    first_ts = last_ts = ""
    rows: list[str] = []
    for ev in evs:
        prov = ev.provenance
        agent = prov.agent or "unknown"
        authors[agent] = authors.get(agent, 0) + 1
        color = _lane_color(agent)
        if not first_ts:
            first_ts = ev.ts
        last_ts = ev.ts
        human, raw = _fmt_ts(ev.ts)
        part = ev.target.path or ev.target.node_id
        reverted = getattr(ev, "reverted", False)
        cls = "commit reverted" if reverted else "commit"
        short = (ev.hash or "")[:7] or f"seq{ev.seq}"
        rationale = (
            f'<span class="rationale">&ldquo;{_esc(prov.rationale)}&rdquo;</span>'
            if prov.rationale else ""
        )
        rows.append(
            f'<li class="{cls}" style="--c:{color}">'
            f'<div class="rail"><span class="node"></span></div>'
            f'<div class="card">'
            f'<div class="r1"><span class="hash">{_esc(short)}</span>'
            f'<span class="kind">{_esc(ev.op.get("kind"))}</span>'
            f'<span class="part">{_esc(part)}</span></div>'
            f'<div class="diff">{_op_summary_html(ev)}</div>'
            f'<div class="m"><span class="who">'
            f'<span class="av" style="background:{color}">{_esc(_initials(agent))}</span>'
            f"{_esc(agent)}</span>"
            f'<span title="{_esc(raw)}">{_esc(human)}</span>'
            f"{(' &middot; ' + rationale) if rationale else ''}</div>"
            f"</div></li>"
        )

    doc = (header or {}).get("doc") if isinstance(header, dict) else None
    filename = (doc or {}).get("filename") if isinstance(doc, dict) else None
    fmt = (doc or {}).get("format") if isinstance(doc, dict) else None
    baseline = (doc or {}).get("baseline_sha256") if isinstance(doc, dict) else None
    disp_title = filename or title

    sub = [f"<b>{len(evs)}</b> change{'' if len(evs) == 1 else 's'}"]
    if fmt:
        sub.append(f"<b>{_esc(fmt)}</b>")
    if first_ts:
        a, _ = _fmt_ts(first_ts)
        b, _ = _fmt_ts(last_ts)
        sub.append(f"{_esc(a)}{'' if a == b else ' → ' + _esc(b)}")
    if baseline:
        sub.append(f"baseline <code>{_esc(str(baseline)[:10])}</code>")

    chips = "".join(
        f'<span class="kx-chip"><span class="av" style="background:{_lane_color(a)}">'
        f'{_esc(_initials(a))}</span>{_esc(a)} · {n}</span>'
        for a, n in sorted(authors.items(), key=lambda kv: -kv[1])
    )

    body = (
        f'<div class="kx-head"><h1 class="kx-title"><span class="dot"></span>'
        f"{_esc(disp_title)}</h1>"
        f'<div class="kx-sub">{" &middot; ".join(sub)}</div>'
        + (f'<div class="kx-authors">{chips}</div>' if chips else "")
        + "</div>"
    )
    graph = (
        f'<ol class="kx">{"".join(rows)}</ol>'
        if rows else '<div class="empty">No changes recorded.</div>'
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_esc(disp_title)}</title><style>{_CSS}</style></head>"
        f"<body>{body}{graph}</body></html>"
    )


def _op_text(op: dict[str, Any]) -> str:
    """A plain-text before→after summary of an op (for ``changex log``)."""
    kind = op.get("kind", "?")
    if kind == "text.insert":
        return f"+ {op.get('text')}"
    if kind == "text.delete":
        return f"- {op.get('before')}"
    if kind == "text.replace":
        return f"{op.get('before')} → {op.get('after')}"
    if kind == "style.change":
        return f"style {op.get('before')} → {op.get('style')}"
    if kind == "node.insert":
        return f"+ ¶ {op.get('value', {}).get('text', '')}"
    if kind == "node.delete":
        return f"- ¶ {op.get('value', {}).get('text', '')}"
    return str(op)


def render_log(events: Iterable[Event], *, oneline: bool = False) -> str:
    """A git-log-style text history of the journal (each edit = a commit)."""
    out: list[str] = []
    for ev in events:
        short = (ev.hash or "")[:9] or f"seq{ev.seq}"
        agent = ev.provenance.agent or "unknown"
        kind = ev.op.get("kind", "?")
        if oneline:
            out.append(f"{short}  {kind:<13} {_op_text(ev.op)}  ({agent}, {ev.ts})")
            continue
        out.append(f"commit {short}  (seq {ev.seq})")
        out.append(f"Author: {agent}" + (f" <{ev.provenance.vendor}>" if ev.provenance.vendor else ""))
        out.append(f"Date:   {ev.ts}")
        out.append(f"Part:   {ev.target.path or ev.target.node_id}")
        if ev.provenance.rationale:
            out.append(f"Why:    {ev.provenance.rationale}")
        out.append("")
        out.append(f"    {kind}  {_op_text(ev.op)}")
        out.append("")
    return "\n".join(out)


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


_CSS = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;font:13px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
     color:#e6e8ef;background:#16181d}
.kx-head{padding:16px 20px;border-bottom:1px solid #2a2d36;
         background:linear-gradient(180deg,#1d2027,#16181d)}
.kx-title{font-size:16px;font-weight:650;color:#f4f6fb;margin:0;display:flex;
          align-items:center;gap:8px}
.kx-title .dot{width:9px;height:9px;border-radius:50%;background:#4dd0e1}
.kx-sub{margin:6px 0 0;color:#9aa0ad;font-size:12px;display:flex;flex-wrap:wrap;gap:6px 14px}
.kx-sub b{color:#c7ccd6;font-weight:600}
.kx-sub code{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:#9aa0ad}
.kx-authors{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.kx-chip{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:#cfd4de;
         background:#23262e;border:1px solid #2f333d;border-radius:999px;padding:2px 9px 2px 3px}
.av{width:18px;height:18px;border-radius:50%;display:inline-flex;align-items:center;
    justify-content:center;font-size:9px;font-weight:700;color:#10121a}
ol.kx{list-style:none;margin:0;padding:6px 0 24px}
li.commit{display:grid;grid-template-columns:46px 1fr;align-items:stretch}
.rail{position:relative;width:46px}
.rail::before{content:"";position:absolute;left:23px;top:0;bottom:0;width:2px;
              background:#2c2f39;transform:translateX(-1px)}
li.commit:first-child .rail::before{top:18px}
li.commit:last-child .rail::before{bottom:auto;height:18px}
.node{position:absolute;left:23px;top:14px;width:13px;height:13px;border-radius:50%;
      transform:translateX(-50%);border:3px solid #16181d;
      background:var(--c);box-shadow:0 0 0 1px var(--c)}
.card{padding:9px 16px 13px 4px;border-bottom:1px solid #1f2229}
li.commit:hover .card{background:#1b1e25}
.r1{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.hash{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:#10121a;
      background:var(--c);border-radius:4px;padding:1px 6px;font-weight:600}
.kind{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:#aeb4c0;
      background:#23262e;border:1px solid #2f333d;border-radius:4px;padding:1px 6px}
.part{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:#7f8696}
.diff{margin:6px 0 5px;color:#d7dbe3;word-break:break-word}
ins{background:rgba(63,185,80,.22);color:#7ee787;text-decoration:none;border-radius:3px;padding:0 3px}
del{background:rgba(248,81,73,.20);color:#ff9d96;border-radius:3px;padding:0 3px}
.m{display:flex;align-items:center;gap:8px;color:#8b91a0;font-size:11px;flex-wrap:wrap}
.who{display:inline-flex;align-items:center;gap:5px;color:#c7ccd6}
.rationale{color:#9aa0ad;font-style:italic}
.reverted .card{opacity:.45}
.reverted ins,.reverted del{text-decoration:line-through}
.empty{padding:28px 20px;color:#8b91a0}
@media(prefers-color-scheme:light){
  body{color:#1f2329;background:#fff}
  .kx-head{background:linear-gradient(180deg,#f6f7f9,#fff);border-color:#e6e8ec}
  .kx-title{color:#11151a}.kx-sub{color:#6b7280}.kx-sub b{color:#374151}
  .kx-chip{background:#f1f3f5;border-color:#e2e5ea;color:#374151}
  .rail::before{background:#e2e5ea}.node{border-color:#fff}
  .card{border-color:#eef0f3}li.commit:hover .card{background:#f8f9fb}
  .kind{background:#f1f3f5;border-color:#e2e5ea;color:#4b5563}.part{color:#9aa1ad}
  .diff{color:#1f2329}ins{color:#1a7f37}del{color:#b42318}.m{color:#6b7280}.who{color:#374151}
}
""".strip()
