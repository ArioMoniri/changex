# ChangeX Architecture

> Status: **draft for review**. This document is the artifact the ML-engineer,
> prompt-engineer, and full-stack reviewers critique before the build proceeds.

## 1. Problem statement

When an AI agent edits an Office document, the user needs an exact, trustworthy
answer to: **"What did the AI change, where, why, and can I accept/reject each
change?"** — for `.docx`, `.xlsx`, `.csv`, `.pptx`, and legacy `.doc`.

Existing tools (mid-2026) fall into two buckets:

- **Diff/redline tools** (Docxodus/python-redlines, Office Diff, Aspose Compare) —
  compare two finished files. Lossy for intent, miss ordering, weak on xlsx/pptx.
- **Word-only AI redliners** (Vesence, Sphere, editGPT, dociq, docx-mcp,
  docx-redline-mcp, adeu) — excellent for `.docx`, but Word-centric and tied to a
  single vendor/flow.

**ChangeX's thesis:** capture the *operation stream* at the moment of editing,
attribute every operation, and render it into whatever review surface the format
supports. Provenance-first, format-complete, vendor-neutral.

## 2. Core principles

1. **Event sourcing.** The source of truth is an append-only journal of operations
   (the `.changex` file). The tracked output document and any review UI are
   *projections* of that journal. (See [CHANGEX_FORMAT.md](CHANGEX_FORMAT.md).)
2. **Two capture modes, one journal.**
   - **Active capture (preferred):** the agent edits through ChangeX tools; each
     tool call appends a fully-attributed operation. True end-to-end tracking.
   - **Passive/baseline capture (fallback):** snapshot the document on `open`,
     semantic-diff on `save`, and synthesize operations. Guarantees coverage even
     when the agent edited via another path.
3. **Canonical document model.** Adapters normalize each format into a shared,
   addressable model so operations and provenance are format-agnostic.
4. **Stable addressing.** Every editable node has a durable `node_id` so operations
   survive re-parsing and can be replayed/rejected deterministically.
5. **Vendor-neutral surface.** MCP first; everything else (Skill, CLI, viewer)
   wraps the same core.

## 3. System overview

```
                ┌──────────────────────────────────────────────┐
   Claude /     │                changex-mcp                    │
   Gemini /     │  open_tracked · edit · save_tracked ·         │
   OpenAI  ───▶ │  get_changes · render_review · accept/reject  │
   (MCP client) └───────────────┬──────────────────────────────┘
                                 │  uses
                ┌────────────────▼──────────────────────────────┐
                │                 changex-core                   │
                │                                                │
                │  Adapters ──▶ Canonical Model ──▶ Journal      │
                │  (docx/xlsx/    (addressable      (.changex,    │
                │   pptx/csv/doc)  nodes)            event log)   │
                │                      │                          │
                │   Diff (baseline) ◀──┘   Renderers ──▶ tracked  │
                │                                        output    │
                └────────────────────────────────────────────────┘
                                 │ projections
            ┌────────────────────┼─────────────────────────────┐
            ▼                    ▼                              ▼
   tracked .docx/.xlsx/    .changex journal              changex-viewer
   .pptx (native marks)    (portable provenance)         (Tauri review app)
```

## 4. Component design

### 4.1 Canonical document model (`core/model`)
A normalized tree of addressable nodes. Node kinds span formats:

| Format | Primary node kinds |
|--------|--------------------|
| docx   | `paragraph`, `run`, `table`, `row`, `cell`, `style`, `section` |
| xlsx   | `sheet`, `cell`, `row`, `column`, `named_range`, `chart`, `formula` |
| pptx   | `slide`, `shape`, `text_frame`, `paragraph`, `run`, `table`, `image` |
| csv    | `row`, `cell`, `header` |

Each node: `{ node_id, kind, path, value, attrs, children }`. `node_id` is a
content+position hash stabilized across re-parses (see addressing strategy in
CHANGEX_FORMAT.md).

### 4.2 Adapters (`core/adapters`)
One adapter per format, each implementing a common `DocumentAdapter` interface:
`load() · to_model() · apply(op) · render_tracked() · save()`.

- **docx** — `python-docx` + `lxml`; native revisions via `<w:ins>`/`<w:del>`
  (building on `docx-revisions` / `python-redlines` techniques).
- **xlsx** — `openpyxl`; changes rendered as cell fills + threaded comments +
  a "Changes" audit sheet (xlsx has no robust native track-changes).
- **pptx** — `python-pptx`; no native track-changes → semantic change overlay
  (annotation shapes + a generated "Revisions" slide/notes) plus the journal.
- **csv** — stdlib; row/cell ops; rendered as a unified or side-by-side redline.
- **doc (legacy)** — convert to docx via LibreOffice headless on ingest, track in
  docx, optionally convert back. Documented as best-effort.

### 4.3 Journal (`core/journal`)
Append-only JSONL event store. Each event = one operation with provenance. Supports
`append`, `replay`, `revert(op_id)`, `squash`, and `verify` (hash-chained for
tamper-evidence). This is the `.changex` sidecar — the portable, format-independent
truth. Spec: [CHANGEX_FORMAT.md](CHANGEX_FORMAT.md).

### 4.4 Diff / baseline reconstruction (`core/diff`)
Semantic, model-aware diff between the `open` snapshot and the `save` state, used
only in passive mode (or to reconcile out-of-band edits). Produces the same
operation vocabulary as active capture, so downstream renderers don't care which
mode produced the ops. Text uses token/sentence-level alignment; tables/cells use
key-based matching; slides use shape-identity matching.

### 4.5 Renderers (`core/render`)
Project the journal onto a review surface:
- **Native track changes** (docx) — accept/reject-able revisions with author =
  model name, timestamp, and a comment carrying the prompt/rationale.
- **Annotated workbook** (xlsx) — colored cells, threaded comments, audit sheet.
- **Semantic overlay** (pptx) — revision callouts + generated summary slide/notes.
- **Unified/side-by-side HTML redline** — used by the viewer and the CLI report.

### 4.6 MCP server (`packages/mcp`)
The universal integration. Tools (initial set):

| Tool | Purpose |
|------|---------|
| `open_tracked(path)` | Open a doc, snapshot baseline, start a session, return a handle + model summary |
| `get_outline(handle)` | Return the addressable node outline for the agent to target edits |
| `edit(handle, op)` | Apply one semantic operation; append to journal with provenance |
| `save_tracked(handle, out)` | Render native track changes + write `.changex` sidecar |
| `get_changes(handle)` | Return the provenance journal (structured) |
| `render_review(handle, fmt)` | Produce an HTML/markdown review report |
| `accept`/`reject(handle, op_id)` | Resolve individual changes |

Provenance (model id, session, prompt hash, tool-call id, timestamp) is captured
from the MCP call context automatically so the agent doesn't have to self-report.

### 4.7 Surfaces — "native to any model, local or cloud"

ChangeX must attach to whatever model the user already runs, without per-vendor work
and **without requiring the model to be tool-capable.** Three integration tiers:

- **Tier 1 — MCP server (active capture).** The universal tool seam. Works with any
  MCP client: Claude (Code/Desktop), OpenAI (Agents/Responses), Gemini CLI, Cursor,
  Cline, Continue, LibreChat, Open WebUI, and local runners (Ollama / LM Studio behind
  an MCP-capable client). The agent edits through the tools → provenance is captured
  at the source.
- **Tier 2 — `changex` CLI / "wrap any model" (passive capture).** For ANY model,
  including local/offline ones that can't reliably call tools: `changex open <file>`
  snapshots the baseline; the model edits the file however it likes (chat, script,
  add-in, copy back); `changex seal <file>` reconstructs the attributed operation
  journal via semantic diff. No tool-calling, no SDK, no vendor — works with a
  llama.cpp model and a text box. This is the "native to anything" guarantee.
- **Tier 3 — Library / SDK.** `import changex_core` to embed tracking in a custom
  agent or pipeline.

**Visualization is decoupled from integration** and intentionally lightweight — pick
whichever fits the moment:

- **Self-contained HTML report** — `changex report` emits a single `report.html`
  (no server, no deps) to open locally, attach to an email, or host as a link.
- **Local web server** — `changex view` serves an interactive localhost page (inline
  + side-by-side, accept/reject, provenance timeline filterable by model). LAN-shareable;
  nothing leaves the machine.
- **Native in-file track changes** — the document itself (Word revisions, annotated
  workbook, pptx overlay).
- **Optional desktop app** — the Tauri viewer (`packages/viewer`) for users who want
  an installable local app; it reuses the same HTML/webserver renderer, the Python
  core as a sidecar.

- **Claude Skill** (`skill/`) — packages the CLI for Claude Code/Desktop users.

## 5. Cross-model integration — local or cloud, tool-capable or not

| Model surface | Primary attach | Capture mode |
|---------------|----------------|--------------|
| Claude (Code/Desktop/API) | MCP server (or Skill) | active |
| OpenAI (Agents/Responses/Codex) | MCP server | active |
| Gemini (CLI/API) | MCP server | active |
| Cursor / Cline / Continue / LibreChat / Open WebUI | MCP server | active |
| Local models (Ollama, LM Studio, llama.cpp) | MCP if the client supports it, **else** `changex open`/`seal` CLI | active or passive |
| Any other tool / human-in-the-loop | `changex open`/`seal` CLI, or import core | passive |

The contract is identical across vendors when tools are available: edit through the
tools → provenance is free. When the model is local, offline, or not tool-capable,
the Tier-2 CLI wrap produces the **same** journal and the **same** visualizations
from just the before/after files — so ChangeX is genuinely native to *any* model.

## 6. Tech stack & rationale

- **Core + MCP: Python.** The OOXML manipulation ecosystem (`python-docx`,
  `openpyxl`, `python-pptx`, `lxml`, plus `docx-revisions`/`python-redlines`) is by
  far the richest, keeping the project single-language and low-friction.
- **MCP SDK:** official `mcp` Python SDK / FastMCP.
- **Viewer: Tauri v2 + React + TypeScript.** Tiny binary, local-only (documents
  never leave the machine), Python core as a sidecar.
- **Constraints (from project conventions):** files < 500 lines, typed public
  interfaces, DDD bounded contexts (adapter / journal / render / diff), input
  validation + path sanitization at every boundary.

## 7. Key risks & open questions (for reviewers)

1. **Stable node addressing** across re-parses and large structural edits — the
   linchpin for deterministic replay/reject. Is a content+position hash enough, or
   do we need an injected-id strategy (and how to keep files clean)?
2. **Active vs passive coverage.** How much can we rely on agents editing *through*
   the tools vs. needing robust passive diff? What's the MVP cut?
3. **pptx review UX** without native track-changes — overlay vs. summary vs. journal-only.
4. **Provenance trust.** Tamper-evidence (hash chain) vs. signing; what do regulated
   users actually need?
5. **Prompt/tool ergonomics** — will models reliably choose semantic `edit` ops over
   blunt full-rewrites? (Prompt-engineering reviewer to weigh in.)
6. **Performance** on large workbooks/decks; streaming vs. whole-file.
