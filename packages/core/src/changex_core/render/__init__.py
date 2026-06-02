"""Render projections of the journal, and the per-format render dispatch.

Two kinds of rendering live under ``render``:

1. **Format-agnostic journal projections** — :func:`render_html` /
   :func:`render_markdown` walk the journal events and emit an inline redline +
   provenance report. These are identical for every format and are exported here.

2. **Native / overlay tracked output** — the format-specific review surface
   (docx Word revisions; xlsx/csv/pptx non-native overlays). This is produced by
   the *adapter*, not by a standalone renderer: the journal is replayed onto a
   fresh adapter and the adapter emits the tracked bytes.

Render dispatch convention (for phase-2 format agents)
------------------------------------------------------
There is no separate renderer registry: the tracked-output renderer for a format
*is* its adapter. To save a tracked document for any format, callers go through
:func:`changex_core.adapters.load_adapter` (extension -> adapter) and then:

    adapter = load_adapter(baseline_path)        # extension picks the adapter
    baseline = adapter.to_model()
    journal.replay(adapter, baseline)            # applies only active ops
    adapter.save(out_path)                        # -> adapter.render_tracked()

``DocumentAdapter.render_tracked() -> bytes`` is the single dispatch point each
adapter implements:

* docx       -> native ``w:ins`` / ``w:del`` revision XML (real accept/reject)
* xlsx / csv -> a non-native overlay (colored cells / comments / audit sheet;
                csv redline) — see docs/FIDELITY.md; the journal is authoritative
* pptx       -> a non-native overlay (revision callouts / summary slide)

:func:`changex_core.render.save.save_active` implements exactly this replay-then-
save flow for docx today (constructing :class:`DocxAdapter` directly). A phase-2
agent generalizes it by swapping that construction for ``load_adapter`` so the
same replay logic drives every format by extension — the journal/replay contract
above does not change.
"""

from __future__ import annotations

from changex_core.render.html import render_html, render_markdown

__all__ = ["render_html", "render_markdown"]
