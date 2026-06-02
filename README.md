# ChangeX

**Provenance-first change tracking for AI document edits.**

ChangeX records *exactly* what an LLM (Claude, Gemini, OpenAI, or any MCP-capable
agent) changed in an Office document — `.docx`, `.xlsx`, `.csv`, `.pptx`, `.doc` —
**end to end, as the edits happen**, not by diffing two files after the fact.

Every change is captured as a structured, attributable operation: *what* changed,
*where*, *which model/agent/prompt* produced it, and *when*. ChangeX then renders
that history several ways:

1. **Native track changes inside the file** — real Word revisions (`<w:ins>`/`<w:del>`).
   (Cell-level annotations + comments for Excel and a semantic overlay for PowerPoint
   are designed but **planned** — see [docs/FIDELITY.md](docs/FIDELITY.md).)
2. **A portable sidecar journal** (`.changex`) — an event-sourced, hash-chained log
   of every operation with provenance, independent of the document format.
3. **Lightweight visualization, your choice** —
   - a **single-file HTML report** (`changex review --out review.html`): no server,
     no deps, open locally or share as a link;
   - a **local review webserver** (`changex view`): an interactive `127.0.0.1` page
     with inline + side-by-side redline, a provenance timeline filterable by
     model/seq, and live accept/reject — nothing leaves the machine;
   - the document's **own native track changes** in Word;
   - an **optional desktop app** (Tauri, `packages/viewer`) over the same renderer.

## Why not just diff the files?

A diff answers "how do these two files differ." ChangeX answers
**"what did the AI actually do, in order, and why."** In active capture it records the
operation stream live (insert paragraph, set cell `B7=...`, delete slide 3, restyle
run), attributes each op to a model/turn/prompt, and can replay or selectively roll
back. When an edit happens outside the tracked tools, the `open`/`seal` fallback
reconstructs the operations by diff — faithfully recovering *what* changed, though in
that mode the *who/why* is unknown (honest, degraded provenance — see
[docs/FIDELITY.md](docs/FIDELITY.md)).

## How it integrates with the models — native to any model

ChangeX is native to *any* model through **two interchangeable paths** that produce
the **same** `.changex` journal and the **same** visualizations:

- **MCP active-capture** — the **MCP server** is the vendor-neutral seam across
  Claude, Gemini, OpenAI, Cursor, Cline, and any MCP client. The agent opens, edits,
  and saves *through* ChangeX tools, so provenance is captured at the source.
- **`changex open` / `seal` passive-capture** — for ANY model, including local/offline
  ones that can't call tools (Ollama, LM Studio, llama.cpp) and human-in-the-loop:
  `changex open` snapshots a baseline, anything edits the file in place, and
  `changex seal` reconstructs the attributed journal by diff. No SDK, no tool-calling.
  Provenance is honestly **degraded** in this mode (who/why unknown) — see
  [docs/FIDELITY.md](docs/FIDELITY.md).

A Claude **Skill** and a thin **CLI** wrap the same core. Copy-paste config for every
surface is in [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Status

🚧 Early build. **Available today:** the `.docx` spine end-to-end — MCP active-capture,
`changex open`/`seal` passive-capture, the `.changex` journal, the single-file HTML
report (`changex review`), and the local review webserver (`changex view`). xlsx /
pptx / csv and the desktop app are **planned**. See
[docs/ROADMAP.md](docs/ROADMAP.md) for milestones, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for the design, and [docs/FIDELITY.md](docs/FIDELITY.md) for the honest per-format and
per-capture-mode limits.

## Repo layout

```
packages/core     changex-core   — canonical model, adapters, journal, renderers, diff (Python)
packages/mcp      changex-mcp    — MCP server exposing tracked open/edit/save tools (Python)
packages/viewer   changex-viewer — Tauri + React desktop review app
skill/            Claude Skill packaging of the core
docs/             roadmap, architecture, .changex format spec, integration guide, fidelity/limits
examples/         sample documents and tracked sessions
```

## License

MIT (intended).
