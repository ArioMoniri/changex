"""Non-native csv overlay renderer: unified + side-by-side HTML redline.

Honesty (read this)
-------------------
csv has **no in-file revision concept whatsoever** — a ``.csv`` is plain rows of
plain values. There is nothing analogous to Word's accept/reject. The review
surface is therefore entirely the ``.changex`` journal plus this projection: an
HTML page showing a **unified** redline (changed cells inline, before crossed out
/ after inserted) and a **side-by-side** baseline-vs-current grid. The journal is
the authoritative record; this is a human-readable lens onto it.

This renderer is pure string assembly with HTML-escaping — no network, no I/O.
The csv adapter's ``render_tracked()`` returns the bytes of this HTML.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

_CSS = """
body { font: 13px/1.5 -apple-system, Segoe UI, Roboto, sans-serif; margin: 1.5rem; }
h1 { font-size: 1.3rem; } h2 { font-size: 1rem; margin-top: 1.4rem; }
table { border-collapse: collapse; margin: .4rem 0; }
td, th { border: 1px solid #ddd; padding: .25rem .5rem; vertical-align: top; }
th { background: #f6f8fa; text-align: left; }
ins { background: #e6ffed; text-decoration: none; }
del { background: #ffeef0; }
.changed { outline: 2px solid #f0b429; }
.rowins { background: #e6ffed; } .rowdel { background: #ffeef0; }
.rownum { color: #888; background: #fafafa; text-align: right; }
.note { color: #666; font-size: .85rem; }
""".strip()


@dataclass(frozen=True)
class CellEdit:
    """A directly-edited cell for the unified redline. ``row``/``col`` are 0-based."""

    row: int
    col: int
    before: str
    after: str


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _grid_html(rows: list[list[str]], *, changed: set[tuple[int, int]]) -> str:
    """Render a grid of ``rows`` with the ``changed`` (row,col) cells outlined."""
    out = ["<table>"]
    for r, row in enumerate(rows):
        out.append("<tr>")
        out.append(f'<td class="rownum">{r + 1}</td>')
        for c, value in enumerate(row):
            cls = ' class="changed"' if (r, c) in changed else ""
            out.append(f"<td{cls}>{_esc(value)}</td>")
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def _unified_html(
    current: list[list[str]],
    edits: dict[tuple[int, int], tuple[str, str]],
    inserted_rows: set[int],
    deleted_rows: list[tuple[int, list[str]]],
) -> str:
    """Render the unified redline: per-cell before/after inline, +/- whole rows."""
    out = ["<table>"]
    for r, row in enumerate(current):
        row_cls = ' class="rowins"' if r in inserted_rows else ""
        out.append(f"<tr{row_cls}>")
        out.append(f'<td class="rownum">{"+" if r in inserted_rows else r + 1}</td>')
        for c, value in enumerate(row):
            edit = edits.get((r, c))
            if edit is not None:
                before, after = edit
                cell = f"<del>{_esc(before)}</del> <ins>{_esc(after)}</ins>"
            else:
                cell = _esc(value)
            out.append(f"<td>{cell}</td>")
        out.append("</tr>")
    for at, values in deleted_rows:
        out.append('<tr class="rowdel">')
        out.append(f'<td class="rownum">-{at}</td>')
        for value in values:
            out.append(f"<td><del>{_esc(value)}</del></td>")
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def build_redline_html(
    baseline_rows: list[list[str]],
    current_rows: list[list[str]],
    cell_edits: list[CellEdit],
    inserted_rows: set[int],
    deleted_rows: list[tuple[int, list[str]]],
    *,
    title: str = "ChangeX CSV review",
) -> str:
    """Assemble the unified + side-by-side HTML redline for a csv journal.

    Args:
        baseline_rows: The csv as it was before any ops (rows of string cells).
        current_rows: The csv after applying the active ops.
        cell_edits: Directly-edited cells (``cell.set`` ops) in current coords.
        inserted_rows: 0-based indices of inserted rows in ``current_rows``.
        deleted_rows: ``(1-based at, prior cell values)`` for each deleted row.
        title: Page title.

    Returns:
        A complete standalone HTML document string.
    """
    edits_map = {(e.row, e.col): (e.before, e.after) for e in cell_edits}
    changed_current = set(edits_map.keys())
    note = (
        "csv has no native track-changes; this redline is a projection of the "
        ".changex journal, which is the authoritative record."
    )
    unified = _unified_html(current_rows, edits_map, inserted_rows, deleted_rows)
    base_grid = _grid_html(baseline_rows, changed=set())
    cur_grid = _grid_html(current_rows, changed=changed_current)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body>"
        f"<h1>{_esc(title)}</h1>"
        f'<p class="note">{_esc(note)}</p>'
        "<h2>Unified redline</h2>"
        f"{unified}"
        "<h2>Side-by-side</h2>"
        "<table><tr>"
        "<th>Baseline</th><th>Current</th></tr><tr>"
        f"<td>{base_grid}</td><td>{cur_grid}</td>"
        "</tr></table>"
        "</body></html>"
    )


__all__ = ["CellEdit", "build_redline_html"]
