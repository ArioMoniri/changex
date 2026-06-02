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

Each node: `{ node_id, node_kind, path, value, attrs, children }`. `node_id` is an
**opaque, edit-invariant** identifier — docx paragraphs reuse Word's native
`w14:paraId`; sub-paragraph nodes get a minted counter id (injected as a bookmark).
A content+position fingerprint is kept only as a *fallback* anchor for fuzzy rebind
(passive mode / lost sidecar), never as the primary key (see CHANGEX_FORMAT.md).

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
`append`, `read`, `replay`, `revert`/`unrevert(op_id)`, and `verify` (RFC 8785 JCS
hash-chain for tamper-evidence; `squash` is planned). This is the `.changex`
sidecar — the portable, format-independent truth. Spec: [CHANGEX_FORMAT.md](CHANGEX_FORMAT.md).

### 4.4 Diff / baseline reconstruction (`core/diff`)
Diff between the `open` snapshot and the `seal` state, used in passive mode (or to
reconcile out-of-band edits). Produces the same operation vocabulary as active
capture, so downstream renderers don't care which mode produced the ops. **Today
(docx):** `difflib.SequenceMatcher` aligns paragraphs, emits intra-paragraph
`text.replace`/`insert`/`delete` for aligned-but-changed paragraphs,
`node.insert`/`node.delete` for added/removed paragraphs, and `style.change` on
style drift; reconstructions replay cleanly onto the baseline. Honest limit: a
delete-plus-add in the same region may align as a single low-similarity
`text.replace` rather than `node.delete`+`node.insert` (see [FIDELITY.md](FIDELITY.md) §2).
Spreadsheet key-based matching and slide shape-identity matching are **planned** with
their adapters (M3/M4).

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
| `accept`/`reject(handle, op_id)` | Resolve individual changes *(planned for MCP; available today in the `changex view` webserver)* |

Provenance is split into **observed** (auto-captured server-side: timestamp, session
id, tool-call/request id, MCP `clientInfo` name/version) and **declared** (model id +
vendor via `agent_context` at `open_tracked`; optional rationale/prompt). Bare MCP does
not carry the user's prompt or conversation turn, so those fields are best-effort and
labeled `provenance_source` — never claimed as "free." See [FIDELITY.md](FIDELITY.md).

### 4.7 Surfaces — "native to any model, local or cloud"

ChangeX must attach to whatever model the user already runs, without per-vendor work
and **without requiring the model to be tool-capable.** Three integration tiers:

- **Tier 1 — MCP server (active capture).** The universal tool seam. Works with any
  MCP client: Claude (Code/Desktop), OpenAI (Agents/Responses), Gemini CLI, Cursor,
  Cline, Continue, LibreChat, Open WebUI, and local runners (Ollama / LM Studio behind
  an MCP-capable client). The agent edits through the tools → provenance is captured
  at the source.
- **Tier 2 — `changex` CLI / "wrap any model" (passive capture). Available for docx.**
  For ANY model, including local/offline ones that can't reliably call tools:
  `changex open <file>` snapshots the baseline (preserving the exact opened bytes in a
  sidecar); the model edits the file however it likes (chat, script, add-in, copy
  back); `changex seal <file>` reconstructs the attributed operation journal via a
  `difflib`-based diff (paragraph alignment + intra-paragraph text edits + node
  insert/delete + style change). No tool-calling, no SDK, no vendor — works with a
  llama.cpp model and a text box. This is the "native to anything" guarantee.
  Reconstructed ops carry **degraded provenance** (agent/turn/prompt `null`,
  `provenance_source="observed"`) — faithful *what*, not *who/why* ([FIDELITY.md](FIDELITY.md)).
- **Tier 3 — Library / SDK.** `import changex_core` to embed tracking in a custom
  agent or pipeline.

**Visualization is decoupled from integration** and intentionally lightweight — pick
whichever fits the moment (the **file**, **link**, and **webserver** surfaces ship
today for docx):

- **Self-contained HTML report (file / link)** — `changex review --out review.html`
  emits a single file (no server, no deps) to open locally, attach to an email, or
  host as a link. **Available.**
- **Local web server** — `changex view` serves an interactive page bound to
  `127.0.0.1` only (inline + side-by-side, live accept/reject, provenance timeline
  filterable by model/agent and by seq). Nothing leaves the machine. **Available.**
- **Native in-file track changes** — the document itself (Word revisions today;
  annotated workbook / pptx overlay planned).
- **Optional desktop app** — the Tauri viewer (`packages/viewer`) for users who want
  an installable local app; it reuses the same HTML/webserver renderer, the Python
  core as a sidecar. **Planned.**

> Honest per-format and per-capture-mode limits (what's Available vs Planned, passive
> = degraded provenance, hash chain = tamper-evidence) are consolidated in
> [FIDELITY.md](FIDELITY.md).

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
