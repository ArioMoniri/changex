"""Thin CLI exercising the M0 spine: ``changex track | review | verify | view``.

This is the script-based acceptance surface for M0. It does not implement the MCP
server (that is the separate ``changex-mcp`` package); it drives the core
directly so the spine can be validated end-to-end from a shell.

Format dispatch: ``track`` / ``verify`` / ``view`` resolve the adapter by the
file's extension via :func:`changex_core.adapters.load_adapter` rather than
hard-coding docx, so a new format adapter (xlsx/csv/pptx) is reachable from the
CLI the moment it is registered. ``.docx`` behavior is unchanged.

All caller paths are sanitized at the boundary (:func:`changex_core.paths.safe_path`
is used by every core entry point this CLI calls).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from changex_core import ui
from changex_core.adapters import SUPPORTED_SUFFIXES, load_adapter
from changex_core.adapters.docx_adapter import DEFAULT_AUTHOR
from changex_core.journal.events import Header, Provenance, Target, utc_now_iso
from changex_core.journal.journal import Journal
from changex_core.ops.vocabulary import op_from_dict, target_node_id
from changex_core.passive import open_passive, seal_passive
from changex_core.paths import safe_path
from changex_core.render.document import render_document_html
from changex_core.render.html import render_html, render_markdown
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


def _doc_format(path) -> str:  # type: ignore[no-untyped-def]
    """Return the document format name for a path (its lowercased suffix sans dot)."""
    return path.suffix.lower().lstrip(".")


def _save_active_via_adapter(
    journal: Journal, baseline: str, out: str, *, author: str
) -> int:
    """Replay the journal's active events onto a fresh adapter and save (any format).

    This is the format-aware analogue of :func:`render.save.save_active`: it loads
    the baseline through :func:`load_adapter` (extension picks the adapter), then
    replays ONLY non-reverted events onto that clean adapter and saves the tracked
    output. Because it replays into a fresh adapter rather than baking the live
    one, a later ``revert`` genuinely drops the op's revision from the saved file.
    For ``.docx`` this is byte-for-byte the existing ``save_active`` flow.
    """
    adapter = load_adapter(baseline, author=author)
    baseline_model = adapter.to_model()
    journal.replay(adapter, baseline_model)
    adapter.save(out)
    return len(journal.active_events())


def cmd_track(args: argparse.Namespace) -> int:
    """Apply a JSON list of ops to a document, writing the tracked doc + .changex.

    Format-aware: the adapter is resolved by the input file's extension via
    :func:`load_adapter` (``.docx`` keeps its exact prior behavior). The output
    must share the input's extension so the tracked projection matches the format.
    """
    doc_path = safe_path(args.docx, must_exist=True, allow_suffixes=SUPPORTED_SUFFIXES)
    ops_path = safe_path(args.ops, must_exist=True, allow_suffixes=(".json",))
    out_path = safe_path(args.out, allow_suffixes=(doc_path.suffix.lower(),))
    changex_path = safe_path(args.changex, allow_suffixes=(".changex", ".jsonl"))

    adapter = load_adapter(str(doc_path), author=args.author)
    header = Header.create(
        baseline_sha256=adapter.baseline_sha256(),
        filename=doc_path.name,
        doc_format=_doc_format(doc_path),
        node_id_map=adapter.node_id_map() if hasattr(adapter, "node_id_map") else {},
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
    # the op's revision from the saved doc (rather than baking in every applied
    # op). With no reverts yet this reproduces the live adapter exactly.
    active = _save_active_via_adapter(
        journal, str(doc_path), str(out_path), author=args.author
    )
    print(f"tracked doc  -> {out_path}")
    print(f".changex     -> {changex_path}")
    print(f"ops applied  : {len(op_dicts)} ({active} active)")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify a .changex hash chain + baseline binding and report the result."""
    changex_path = safe_path(args.changex, must_exist=True, allow_suffixes=(".changex", ".jsonl"))
    journal = Journal.open(str(changex_path))
    baseline = (
        str(safe_path(args.baseline, must_exist=True, allow_suffixes=SUPPORTED_SUFFIXES))
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
    doc_path = getattr(args, "doc", None)
    if args.format == "markdown":
        report = render_markdown(events)
    elif doc_path:
        doc = safe_path(doc_path, must_exist=True, allow_suffixes=SUPPORTED_SUFFIXES)
        if doc.suffix.lower() == ".docx":
            # Show the changes inline in the document's own outline.
            report = render_document_html(str(doc), title="ChangeX review", events=events)
        else:
            # The in-document outline view is docx-only today; fall back to the op log.
            report = render_html(events)
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
        str(safe_path(args.doc, must_exist=True, allow_suffixes=SUPPORTED_SUFFIXES))
        if args.doc
        else None
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
    print(ui.ok("passive session opened") + ui.c("  (capture_mode=passive)", "dim"))
    print(ui.field("baseline", result.baseline.uri))
    print(ui.field("baseline_sha", result.baseline.sha256))
    print(ui.field("paragraphs", result.paragraphs))
    print(ui.field(".changex", result.changex_path))
    print()
    print("  Any model / tool / human may now edit the .docx. Then run:")
    print(ui.cmd(f'changex seal "{args.docx}"'))
    return 0


def cmd_seal(args: argparse.Namespace) -> int:
    """Passive seal: diff current docx vs baseline and append reconstructed ops."""
    result = seal_passive(args.docx, args.changex)
    print(ui.ok("passive seal complete") + ui.c("  (DEGRADED provenance — reconstructed by diff)", "dim"))
    print(ui.field(".changex", result.changex_path))
    if result.baseline_unchanged:
        print("  no changes detected vs baseline; nothing appended.")
        return 0
    print(
        ui.field(
            "ops appended",
            f"{result.appended} (replace={result.replaced}, insert={result.inserted}, "
            f"delete={result.deleted}, style={result.style_changed})",
        )
    )
    if result.tracked_path:
        print(
            ui.field("tracked .docx", result.tracked_path)
            + ui.c("  ← open in Word for native accept/reject", "dim")
        )
    cxp = result.changex_path
    print()
    print("  " + ui.c("See what changed:", "bold"))
    if result.tracked_path:
        print(ui.cmd(f'changex review "{cxp}" --doc "{result.tracked_path}" --out review.html'))
        print(ui.cmd(f'changex view   "{cxp}" --doc "{result.tracked_path}"'))
    else:
        print(ui.cmd(f'changex review "{cxp}" --out review.html'))
        print(ui.cmd(f'changex view   "{cxp}"'))
    print()
    print("  " + ui.warn("provenance is degraded — agent/vendor/turn/prompt are null."))
    return 0


def cmd_shell(args: argparse.Namespace) -> int:
    """Drop into an interactive Python shell with changex_core preloaded."""
    import code

    import changex_core as cx
    from changex_core.adapters import load_adapter

    def load(path: str, **kwargs):
        """load('file.docx') -> a DocumentAdapter for the file (any supported format)."""
        return load_adapter(path, **kwargs)

    ns = {"cx": cx, "load_adapter": load_adapter, "load": load}
    intro = ui.banner("interactive shell — changex_core is loaded")
    intro += (
        "  " + ui.c("cx", "bold", "cyan") + " = changex_core    "
        + ui.c("load('report.docx')", "bold", "cyan") + " -> adapter    "
        + ui.c("Ctrl-D to exit", "dim") + "\n"
    )
    code.interact(banner=intro, local=ns, exitmsg=ui.c("bye 👋", "dim"))
    return 0


_HELP_GROUPS = [
    (
        "Track & review",
        [
            ("track", "apply ops to a doc (.docx/.xlsx/.csv/.pptx/.md/.doc) → tracked file + .changex"),
            ("review", "render an HTML / markdown redline (--doc = inline in the doc's outline)"),
            ("view", "serve an interactive localhost review page (accept / reject)"),
            ("verify", "check a .changex hash chain + baseline"),
        ],
    ),
    (
        "Passive — any model, even offline",
        [
            ("open", "snapshot the baseline before anything edits the file"),
            ("seal", "diff the edited file → reconstruct the tracked changes"),
        ],
    ),
    (
        "Extras",
        [
            ("shell", "interactive Python shell with changex_core preloaded"),
            ("help", "show this command list"),
        ],
    ),
]


def cmd_help(args: argparse.Namespace | None = None) -> int:
    """Show the banner + a grouped, human list of commands ('tasks')."""
    ui.print_banner()
    print(
        "  " + ui.c("changex <command> [options]", "bold")
        + ui.c("   ·   add -h to any command for details", "dim") + "\n"
    )
    for group, items in _HELP_GROUPS:
        print("  " + ui.c(group, "bold", "magenta"))
        for name, desc in items:
            print("    " + ui.c(name.ljust(8), "cyan") + " " + desc)
        print()
    print("  " + ui.c("Update", "bold", "magenta"))
    print("    " + ui.c("pip / uv ", "cyan") + " pip install -U changex  ·  uv tool upgrade changex  ·  pipx upgrade changex")
    print("    " + ui.c("agents   ", "cyan") + " pin the newest in Claude/Cursor/etc:  uvx changex-mcp@latest  (re-add the MCP server)")
    print()
    print(
        ui.c("  docs  ", "dim") + "https://github.com/ArioMoniri/changex/tree/main/docs"
        + ui.c("   ·   ", "dim") + ui.c("changex shell", "cyan") + " to script it"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse CLI parser."""
    parser = argparse.ArgumentParser(prog="changex", description="ChangeX core CLI (M0 spine).")
    try:
        from importlib.metadata import version as _pkg_version

        _v = _pkg_version("changex-core")
    except Exception:  # pragma: no cover
        _v = "unknown"
    parser.add_argument("--version", action="version", version=f"changex {_v}")
    sub = parser.add_subparsers(dest="command", required=True)

    track = sub.add_parser(
        "track",
        help="apply ops to a document (.docx/.xlsx/.csv/.pptx/.md/.doc), emit tracked doc + .changex",
    )
    track.add_argument("docx", help="input document (.docx/.xlsx/.csv/.pptx/.md/.doc)")
    track.add_argument("ops", help="JSON file: list of op dicts")
    track.add_argument("--out", required=True, help="output tracked document (same extension as input)")
    track.add_argument("--changex", required=True, help="output .changex journal")
    track.add_argument("--author", default=DEFAULT_AUTHOR, help="revision author / model name")
    track.set_defaults(func=cmd_track)

    verify = sub.add_parser("verify", help="verify a .changex hash chain + baseline")
    verify.add_argument("changex", help=".changex journal")
    verify.add_argument(
        "--baseline",
        help="baseline document (.docx/.xlsx/.csv/.pptx/.md/.doc) to re-hash against header baseline_sha256",
    )
    verify.set_defaults(func=cmd_verify)

    review = sub.add_parser("review", help="render an HTML/markdown redline")
    review.add_argument("changex", help=".changex journal")
    review.add_argument("--format", choices=["html", "markdown"], default="html")
    review.add_argument(
        "--doc",
        help="tracked .docx — render the changes inline in the document's own outline "
        "(instead of an op-by-op list)",
    )
    review.add_argument("--out", help="write report to this path (else stdout)")
    review.set_defaults(func=cmd_review)

    view = sub.add_parser("view", help="serve an interactive localhost review UI")
    view.add_argument("changex", help=".changex journal")
    view.add_argument(
        "--doc", help="associated tracked document (.docx/.xlsx/.csv/.pptx/.md/.doc) for the page title"
    )
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

    shell = sub.add_parser(
        "shell", help="interactive Python shell with changex_core preloaded (cx, load())"
    )
    shell.set_defaults(func=cmd_shell)

    help_p = sub.add_parser("help", help="show the grouped command list")
    help_p.set_defaults(func=cmd_help)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    argv_list = list(sys.argv[1:] if argv is None else argv)
    if not argv_list:
        return cmd_help()
    args = parser.parse_args(argv_list)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
