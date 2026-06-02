# ChangeX

**Provenance-first change tracking for AI document edits.**

ChangeX records *exactly* what an LLM (Claude, Gemini, OpenAI, or any MCP-capable
agent) changed in an Office document — `.docx`, `.xlsx`, `.csv`, `.pptx`, `.doc` —
**end to end, as the edits happen**, not by diffing two files after the fact.

Every change is captured as a structured, attributable operation: *what* changed,
*where*, *which model/agent/prompt* produced it, and *when*. ChangeX then renders
that history three ways:

1. **Native track changes inside the file** — real Word revisions (`<w:ins>`/`<w:del>`),
   cell-level annotations + comments for Excel, and a semantic change overlay for
   PowerPoint (which has no native track-changes format).
2. **A portable sidecar journal** (`.changex`) — an event-sourced log of every
   operation with full provenance, independent of the document format.
3. **A desktop review app** (Tauri) — inline + side-by-side review, accept/reject,
   and a provenance timeline.

## Why not just diff the files?

A diff answers "how do these two files differ." ChangeX answers
**"what did the AI actually do, in order, and why."** It captures the operation
stream live (insert paragraph, set cell `B7=...`, delete slide 3, restyle run),
attributes each op to a model/turn/prompt, and can replay or selectively roll back.
A semantic-diff fallback reconstructs operations when an edit happened outside the
tracked tools — so coverage is complete either way.

## How it integrates with the models

ChangeX ships as an **MCP server** — the vendor-neutral seam that works across
Claude, Gemini, OpenAI, and any MCP client. The agent opens, edits, and saves the
document *through* ChangeX tools, so provenance is captured at the source. A Claude
**Skill** and a thin **CLI** wrap the same core for users who don't run an MCP client.

## Status

🚧 Early build. See [docs/ROADMAP.md](docs/ROADMAP.md) for milestones and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design.

## Repo layout

```
packages/core     changex-core   — canonical model, adapters, journal, renderers, diff (Python)
packages/mcp      changex-mcp    — MCP server exposing tracked open/edit/save tools (Python)
packages/viewer   changex-viewer — Tauri + React desktop review app
skill/            Claude Skill packaging of the core
docs/             roadmap, architecture, .changex format spec, integration guide
examples/         sample documents and tracked sessions
```

## License

MIT (intended).
