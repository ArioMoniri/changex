# ChangeX Roadmap

> Status: **draft for review.** Milestones are scoped so each one is independently
> demoable. "Most compatible + easiest to use" means: MCP-first (works across
> Claude/Gemini/OpenAI), Python core, native track-changes output, zero-config CLI.

## Guiding cut for the MVP

The single highest-value, lowest-risk end-to-end slice:

> **An agent opens a `.docx` (via the MCP server *or* the `changex open`/`seal`
> CLI), makes edits, and gets back (a) a Word file with native accept/reject
> revisions authored by the model, (b) a portable `.changex` provenance journal,
> and (c) a single-file HTML report you can open or share as a link.**

Two access paths ship together so it's native to *any* model: **MCP** (active
capture, for tool-capable models — Claude / Gemini / OpenAI / local-via-MCP) and the
**`open`/`seal` CLI** (passive capture, for any model including local/offline ones
that just read and write the file). The spreadsheet (`.xlsx`, `.csv`) and presentation
(`.pptx`) formats and the interactive webserver have since **landed** (journal +
non-native overlay; see M3/M4 and M5 below); the desktop app and legacy `.doc` ingest
remain the outstanding extensions.

---

## M0 — Foundations (spine)
**Goal:** the canonical model + journal + docx adapter, exercised by a script.

- `core/model`: addressable node tree + `node_id` strategy.
- `core/journal`: append-only JSONL writer/reader, hash chain, `replay`, `verify`.
- `core/adapters/docx`: load → model → apply text/structural ops → render native
  `<w:ins>`/`<w:del>` revisions → save.
- `.changex` header + op schema (validated, typed).
- **Acceptance:** a Python script applies 5 ops to a sample `.docx`, produces a
  Word file whose revisions accept/reject cleanly, and a `.changex` that `verify`s
  and `replay`s to the same result.

## M1 — Universal integration (MCP + CLI) & the HTML report
**Goal:** any model — tool-capable or not, local or cloud — can track docx edits,
and anyone can see them in a shareable report.

- `packages/mcp`: `open_tracked`, `get_outline`, `edit`, `save_tracked`,
  `get_changes`, `render_review`. Auto-capture provenance (model id, tool-call id,
  prompt hash, timestamp) from MCP call context.
- **`changex` CLI** with the model-agnostic path: `changex open <file>` (snapshot),
  `changex seal <file>` (reconstruct the attributed journal via passive diff),
  `changex review <file> --out review.html` (emit a single-file report).
- Quickstart configs for Claude (Code/Desktop), OpenAI, Gemini CLI, Cursor/Cline,
  and local runners (Ollama / LM Studio via an MCP-capable client).
- **Acceptance:** (1) in an MCP client, edit a real `.docx` → native tracked changes
  + journal; (2) with NO MCP at all, `changex open` → hand/LLM edit → `changex seal`
  produces the same journal; (3) `changex review --out` opens a self-contained HTML
  view, and (4) `changex view` serves the interactive local review page.
  <10-minute setup either way.

## M2 — Passive/baseline diff (coverage guarantee)
**Goal:** track changes even when edits happen outside the tools.

- `core/diff`: semantic text alignment + structural matching → operation stream.
- `open_tracked` snapshots baseline; `save_tracked` reconciles out-of-band edits.
- **Acceptance:** hand-edit the doc between open and save; ChangeX reconstructs the
  correct op stream and renders equivalent tracked changes.

## M3 — Spreadsheets (`.xlsx`, `.csv`) — ✅ Available

> **Status: landed.** `.xlsx` and `.csv` are reachable from the CLI and MCP today.
> Both produce the same `.changex` journal as docx and feed the same
> `review`/`view` surfaces. Because spreadsheets have **no native track-changes**,
> the in-file review is a **non-native overlay**, not host-app accept/reject — see
> [FIDELITY.md](FIDELITY.md) §1.

**Goal:** cell/formula/row-level tracking with a usable review surface.

- `core/adapters/xlsx` (openpyxl): cell/formula/row ops; render = colored cells +
  threaded comments + generated "Changes" audit sheet. ✅
- `core/adapters/csv`: row/cell ops; unified + side-by-side redline. ✅
- **Acceptance (met):** track formula and value edits across sheets; audit sheet
  lists every change with model + timestamp.

## M4 — Presentations (`.pptx`) — ✅ Available

> **Status: landed.** `.pptx` is reachable from the CLI and MCP today, with the
> same journal + `review`/`view` surfaces. PowerPoint has **no native
> track-changes format**, so "accept/reject" is reconstructed from the journal via
> a **non-native overlay**, not a PowerPoint feature — see [FIDELITY.md](FIDELITY.md) §1.

**Goal:** semantic change tracking despite no native track-changes format.

- `core/adapters/pptx` (python-pptx): slide/shape/text ops; render = revision
  callouts + generated "Revisions" summary slide + notes. ✅
- **Acceptance (met):** add/delete/edit slides and shapes; reviewer can see exactly
  what changed per slide and read the journal.

## M5 — Interactive viewer (local webserver) + optional desktop app + legacy `.doc`
**Goal:** a friendly, zero-install review surface, with a desktop app for those who
want one.

> **Status:** the `changex view` webserver landed early (alongside M1) and is
> **available** for docx — `127.0.0.1`-bound interactive page with inline +
> side-by-side redline, live accept/reject (revert/unrevert), and a provenance
> timeline filterable by model/agent and seq. The **desktop app** and **legacy
> `.doc`** ingest below remain planned.

- **`changex view`** (available) — serves an interactive `127.0.0.1` page from a
  `.changex` + doc: inline + side-by-side, live accept/reject, provenance timeline
  filterable by model/agent and seq. Nothing leaves the machine.
- **Optional Tauri desktop app** (`packages/viewer`) — wraps the same renderer/server
  for users who want an installable local app (Python core as a sidecar).
- `.doc` ingest via LibreOffice-headless conversion (best-effort, documented).
- **Acceptance:** `changex view` opens a working review page from a tracked session;
  the desktop app shows the same; accept/reject + export work.

## M6 — Hardening & distribution
**Goal:** trustworthy and installable.

- Tamper-evidence (hash chain + optional signing), provenance verification CLI.
- Packaging: `pip install changex`, `uvx changex-mcp`, signed viewer builds,
  Claude Skill in `skill/`.
- Test corpus of real-world docs; perf budget for large files; docs site.
- **Acceptance:** one-command install for each surface; CI green on the corpus.

---

## Sequencing rationale
- **M0→M1 first** because docx native track-changes + MCP is the differentiated,
  demoable spine and the most-compatible integration.
- **M2 early** because coverage (passive diff) is what makes the tool trustworthy
  beyond cooperative agents.
- **xlsx/pptx (M3/M4)** are the underserved markets — sequenced after the spine so
  they reuse the journal + render contracts rather than reinventing them. **Both have
  since landed** as journal + non-native overlay (no native track-changes exists for
  those formats).
- **Viewer (M5)** is UX polish on top of a proven core, not a prerequisite.

## Non-goals (initially)
- Real-time collaborative editing / multi-user merge (CRDT) — journal is designed
  to allow it later, but it's out of MVP scope.
- A full Office renderer — we lean on native Office + lightweight web preview.
- Cloud storage / SaaS — local-first; documents never leave the machine.
