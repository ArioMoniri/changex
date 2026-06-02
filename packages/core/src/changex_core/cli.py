"""Thin CLI exercising the M0 spine: ``changex track | review | verify``.

This is the script-based acceptance surface for M0. It does not implement the MCP
server (that is the separate ``changex-mcp`` package); it drives the core
directly so the spine can be validated end-to-end from a shell.

All caller paths are sanitized at the boundary (:func:`changex_core.paths.safe_path`
is used by every core entry point this CLI calls).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from changex_core.adapters.docx_adapter import DEFAULT_AUTHOR, DocxAdapter
from changex_core.journal.events import Header, Provenance, Target, utc_now_iso
from changex_core.journal.journal import Journal
from changex_core.ops.vocabulary import op_from_dict, target_node_id
from changex_core.passive import open_passive, seal_passive
from changex_core.paths import safe_path
from changex_core.render.html import render_html, render_markdown
from changex_core.render.save import save_active
from changex_core.render.server import DEFAULT_PORT, serve


def _provenance(session_id: str, agent: str | None, rationale: str | None) -> Provenance:
    return Provenance(
        ts=utc_now_iso(),
        session_id=session_id,
        agent=agent,
        vendor="cli" if agent else None,
        rationale=rationale,
        provenance_source="declared" if agent else "observed",
    )


def cmd_track(args: argparse.Namespace) -> int:
    """Apply a JSON list of ops to a .docx, writing tracked docx + .changex."""
    doc_path = safe_path(args.docx, must_exist=True, allow_suffixes=(".docx",))
    ops_path = safe_path(args.ops, must_exist=True, allow_suffixes=(".json",))
    out_path = safe_path(args.out, allow_suffixes=(".docx",))
    changex_path = safe_path(args.changex, allow_suffixes=(".changex", ".jsonl"))

    adapter = DocxAdapter.load(str(doc_path), author=args.author)
    header = Header.create(
        baseline_sha256=adapter.baseline_sha256(),
        filename=doc_path.name,
        node_id_map=adapter.node_id_map(),
    )
    journal = Journal.open(str(changex_path), header=header)
    session_id = header.session_id

    op_dicts = json.loads(ops_path.read_text(encoding="utf-8"))
    for raw in op_dicts:
        # `rationale` is provenance, not op payload; pull it out before parsing.
        rationale = raw.pop("rationale", None)
        op = op_from_dict(raw)
        adapter.apply(op)
        node_id = target_node_id(op) or ""
        node = adapter.resolve(node_id)
        target = Target(
            node_id=node_id,
            node_kind=(node.node_kind.value if node else raw.get("node_kind", "paragraph")),
            path=(node.path if node else ""),
        )
        journal.append(op, target, _provenance(session_id, args.author, rationale))

    # Save by replaying ONLY the journal's active (non-reverted) events onto a
    # fresh adapter loaded from the baseline, so a later revert genuinely drops
    # the op's revision from the saved .docx (rather than baking in every applied
    # op). With no reverts yet this reproduces the live adapter exactly.
    active = save_active(journal, str(doc_path), str(out_path), author=args.author)
    print(f"tracked docx -> {out_path}")
    print(f".changex     -> {changex_path}")
    print(f"ops applied  : {len(op_dicts)} ({active} active)")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify a .changex hash chain + baseline binding and report the result."""
    changex_path = safe_path(args.changex, must_exist=True, allow_suffixes=(".changex", ".jsonl"))
    journal = Journal.open(str(changex_path))
    baseline = (
        str(safe_path(args.baseline, must_exist=True, allow_suffixes=(".docx",)))
        if args.baseline
        else None
    )
    result = journal.verify(baseline_path=baseline)
    if not result.ok:
        print(
            f"FAIL: chain broken at seq={result.broken_at_seq}: {result.detail}",
            file=sys.stderr,
        )
        return 1
    if not result.baseline_match:
        print(f"FAIL: {result.detail}", file=sys.stderr)
        return 1
    print(f"OK: {changex_path} verifies ({journal.last_seq} ops)")
    print(f"  baseline: {result.detail}")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    """Render an HTML or markdown redline of a .changex journal."""
    changex_path = safe_path(args.changex, must_exist=True, allow_suffixes=(".changex", ".jsonl"))
    journal = Journal.open(str(changex_path))
    events = journal.active_events()
    if args.format == "markdown":
        report = render_markdown(events)
    else:
        report = render_html(events)
    if args.out:
        out = safe_path(args.out)
        out.write_text(report, encoding="utf-8")
        print(f"review -> {out}")
    else:
        print(report)
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    """Serve the interactive localhost review UI for a .changex journal."""
    changex_path = safe_path(args.changex, must_exist=True, allow_suffixes=(".changex", ".jsonl"))
    doc_path = (
        str(safe_path(args.doc, must_exist=True, allow_suffixes=(".docx",))) if args.doc else None
    )
    serve(
        str(changex_path),
        port=args.port,
        open_browser=not args.no_open,
        doc_path=doc_path,
    )
    return 0


def cmd_open(args: argparse.Namespace) -> int:
    """Passive open: snapshot the baseline and write a pending passive header."""
    result = open_passive(args.docx, args.changex)
    print(f"passive session opened (capture_mode=passive)")
    print(f"  baseline    : {result.baseline.uri}")
    print(f"  baseline_sha: {result.baseline.sha256}")
    print(f"  paragraphs  : {result.paragraphs}")
    print(f"  .changex    : {result.changex_path}")
    print("  any model/tool/human may now edit the .docx; run `changex seal` after.")
    return 0


def cmd_seal(args: argparse.Namespace) -> int:
    """Passive seal: diff current docx vs baseline and append reconstructed ops."""
    result = seal_passive(args.docx, args.changex)
    print("passive seal complete (DEGRADED provenance — reconstructed by diff)")
    print(f"  .changex      : {result.changex_path}")
    if result.baseline_unchanged:
        print("  no changes detected vs baseline; nothing appended.")
        return 0
    print(
        f"  ops appended  : {result.appended} "
        f"(replace={result.replaced}, insert={result.inserted}, "
        f"delete={result.deleted}, style={result.style_changed})"
    )
    print("  NOTE: provenance is degraded — agent/vendor/turn/prompt are null,")
    print("        provenance_source='observed', rationale='reconstructed by passive diff'.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse CLI parser."""
    parser = argparse.ArgumentParser(prog="changex", description="ChangeX core CLI (M0 spine).")
    sub = parser.add_subparsers(dest="command", required=True)

    track = sub.add_parser("track", help="apply ops to a .docx, emit tracked docx + .changex")
    track.add_argument("docx", help="input .docx")
    track.add_argument("ops", help="JSON file: list of op dicts")
    track.add_argument("--out", required=True, help="output tracked .docx")
    track.add_argument("--changex", required=True, help="output .changex journal")
    track.add_argument("--author", default=DEFAULT_AUTHOR, help="revision author / model name")
    track.set_defaults(func=cmd_track)

    verify = sub.add_parser("verify", help="verify a .changex hash chain + baseline")
    verify.add_argument("changex", help=".changex journal")
    verify.add_argument(
        "--baseline", help="baseline .docx to re-hash against header baseline_sha256"
    )
    verify.set_defaults(func=cmd_verify)

    review = sub.add_parser("review", help="render an HTML/markdown redline")
    review.add_argument("changex", help=".changex journal")
    review.add_argument("--format", choices=["html", "markdown"], default="html")
    review.add_argument("--out", help="write report to this path (else stdout)")
    review.set_defaults(func=cmd_review)

    view = sub.add_parser("view", help="serve an interactive localhost review UI")
    view.add_argument("changex", help=".changex journal")
    view.add_argument("--doc", help="associated tracked .docx (for the page title)")
    view.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="localhost port (default 8765)"
    )
    view.add_argument(
        "--no-open", action="store_true", help="do not auto-open the browser"
    )
    view.set_defaults(func=cmd_view)

    open_p = sub.add_parser(
        "open", help="passive: snapshot baseline + write a pending passive header"
    )
    open_p.add_argument("docx", help="baseline .docx to open for passive capture")
    open_p.add_argument("--changex", help="output .changex (default: next to the docx)")
    open_p.set_defaults(func=cmd_open)

    seal = sub.add_parser(
        "seal", help="passive: diff current docx vs baseline -> reconstructed ops"
    )
    seal.add_argument("docx", help="the (now edited) .docx to seal")
    seal.add_argument("--changex", help="the .changex from `open` (default: next to the docx)")
    seal.set_defaults(func=cmd_seal)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
