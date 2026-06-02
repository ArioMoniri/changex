#!/usr/bin/env python3
"""End-to-end ChangeX M0 spine example.

What this script demonstrates against the *public* ``changex_core`` API:

1. Open ``examples/sample.docx`` through :class:`changex_core.DocxAdapter`
   (paragraph node_ids reuse Word's native ``w14:paraId``).
2. Open an append-only ``.changex`` journal whose header pins the baseline
   sha256 + the ``node_id -> carrier`` map.
3. Apply ~5 narrowly-typed semantic ops — including **two edits to the same
   paragraph** plus an **insert above** it — recording each in the journal with
   split observed/declared provenance.
4. Save a Word file with native ``w:ins``/``w:del`` revisions authored by the
   model, alongside the ``.changex`` provenance sidecar.
5. ``verify()`` the hash chain and ``replay()`` the journal onto the baseline to
   prove it reproduces the live model.
6. Print the HTML (and markdown) redline review surface.

This is the M0 acceptance walk-through; it touches only public API and writes
into ``examples/out/``. Run with the sample fixture present::

    python scripts/make_sample_docx.py   # if examples/sample.docx is missing
    python examples/track_docx.py
"""

from __future__ import annotations

from pathlib import Path

import changex_core as cx
from changex_core.journal.events import utc_now_iso

_HERE = Path(__file__).resolve().parent
_SAMPLE = _HERE / "sample.docx"
_OUT_DIR = _HERE / "out"

_AGENT = "claude-opus-4-8"
_VENDOR = "anthropic"


def _provenance(journal: cx.Journal, rationale: str) -> cx.Provenance:
    """Build a declared-provenance record for an agent-authored op."""
    return cx.Provenance(
        ts=utc_now_iso(),
        session_id=journal.header.session_id,
        agent=_AGENT,
        vendor=_VENDOR,
        rationale=rationale,
        provenance_source="declared",
    )


def _target(node_id: str, *, kind: str = "paragraph") -> cx.Target:
    return cx.Target(node_id=node_id, node_kind=kind, path="")


def _record(
    adapter: cx.DocxAdapter,
    journal: cx.Journal,
    op: cx.Op,
    *,
    node_id: str,
    kind: str,
    rationale: str,
) -> cx.Event:
    """Apply an op to the live model AND append it to the journal."""
    adapter.apply(op)
    return journal.append(op, _target(node_id, kind=kind), _provenance(journal, rationale))


def run(sample: Path = _SAMPLE, out_dir: Path = _OUT_DIR) -> dict[str, object]:
    """Execute the full track -> save -> verify -> replay -> render walk."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tracked_path = out_dir / "tracked.docx"
    changex_path = out_dir / "session.changex"
    html_path = out_dir / "review.html"
    doc_html_path = out_dir / "document-review.html"
    # Start from a clean journal each run so the example is reproducible.
    if changex_path.exists():
        changex_path.unlink()

    # 1. Open the document and capture the immutable baseline model for replay.
    adapter = cx.DocxAdapter.load(str(sample), author=_AGENT)
    baseline_model = cx.Node.from_dict(adapter.to_model().to_dict())
    paras = adapter.to_model().child_paragraphs()
    heading_id = paras[0].node_id  # the "Quarterly Report" heading
    body_id = paras[1].node_id  # the quick-brown-fox sentence

    # 2. Open the journal, pinning the baseline + node_id map in the header.
    header = cx.Header.create(
        baseline_sha256=adapter.baseline_sha256(),
        filename=sample.name,
        node_id_map=adapter.node_id_map(),
    )
    journal = cx.Journal.open(str(changex_path), header=header)

    # 3. Apply ~5 semantic ops. Two of them edit the SAME body paragraph, and one
    #    inserts a brand-new paragraph above it — exercising stable addressing.
    events: list[cx.Event] = []
    events.append(
        _record(
            adapter,
            journal,
            cx.TextReplace(node_id=body_id, before="quick", after="swift"),
            node_id=body_id,
            kind="paragraph",
            rationale="tighten wording: quick -> swift",
        )
    )
    events.append(
        _record(
            adapter,
            journal,
            cx.TextReplace(node_id=body_id, before="lazy", after="sleepy"),
            node_id=body_id,
            kind="paragraph",
            rationale="second edit to the same paragraph: lazy -> sleepy",
        )
    )
    events.append(
        _record(
            adapter,
            journal,
            cx.StyleChange(node_id=heading_id, style="Heading 2", before="Heading 1"),
            node_id=heading_id,
            kind="paragraph",
            rationale="demote heading level",
        )
    )
    events.append(
        _record(
            adapter,
            journal,
            cx.NodeInsert(
                node_kind="paragraph",
                position=1,  # above the body paragraph
                value={"text": "Executive summary follows.", "style": "Normal"},
            ),
            node_id="(inserted)",
            kind="paragraph",
            rationale="insert an executive-summary paragraph above the body",
        )
    )
    events.append(
        _record(
            adapter,
            journal,
            cx.TextInsert(
                node_id=body_id,
                before_anchor="morning",
                text=" without fail",
            ),
            node_id=body_id,
            kind="paragraph",
            rationale="add emphasis after the existing anchor",
        )
    )

    # 4. Save the native-revision Word file (the .changex was flushed per-append).
    adapter.save(str(tracked_path))

    # 5. Verify the hash chain, then replay onto the baseline via a fresh adapter.
    verify_result = journal.verify()
    replay_adapter = cx.DocxAdapter.load(str(sample), author=_AGENT)
    replayed = journal.replay(replay_adapter, baseline_model)
    live_text = {p.node_id: p.text() for p in adapter.to_model().child_paragraphs()}
    replay_text = {p.node_id: p.text() for p in replayed.child_paragraphs()}
    replay_matches = live_text == replay_text

    # 6. Render the HTML + markdown redline review surfaces.
    html = cx.render_html(journal.active_events(), title="ChangeX M0 demo review")
    markdown = cx.render_markdown(journal.active_events(), title="ChangeX M0 demo review")
    html_path.write_text(html, encoding="utf-8")
    # Document-outline view: the changes shown inline in the file's own structure.
    doc_html = cx.render_document_html(
        str(tracked_path), title="ChangeX M0 demo review", events=journal.active_events()
    )
    doc_html_path.write_text(doc_html, encoding="utf-8")

    print("=== ChangeX M0 end-to-end example ===")
    print(f"baseline sha256 : {adapter.baseline_sha256()[:16]}...")
    print(f"ops applied     : {len(events)}")
    print(f"tracked docx    : {tracked_path}")
    print(f"changex journal : {changex_path}")
    print(f"verify().ok     : {verify_result.ok}")
    print(f"replay matches  : {replay_matches}")
    print(f"html review     : {html_path}")
    print(f"document review : {doc_html_path}  (changes inline in the doc outline)")
    print()
    print("--- markdown redline ---")
    print(markdown)
    print("--- html redline (first 600 chars) ---")
    print(html[:600])

    return {
        "tracked_path": str(tracked_path),
        "changex_path": str(changex_path),
        "html_path": str(html_path),
        "verify_ok": verify_result.ok,
        "replay_matches": replay_matches,
        "ops": len(events),
    }


if __name__ == "__main__":
    run()
