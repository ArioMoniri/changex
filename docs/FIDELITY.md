# ChangeX Fidelity & Limits

> Status: **honest capability statement.** This is the document reviewers asked
> for: a per-format capability matrix and the explicit limits, with nothing
> oversold. If a row says Planned, the code path does not exist yet; an Available
> row is reachable from the CLI/MCP today. If a guarantee is qualified, the
> qualification is load-bearing — read it. **"Available" never means native
> accept/reject** unless the row says so — for xlsx/csv/pptx/md it means journal +
> non-native overlay.

ChangeX renders an operation journal onto whatever review surface a format
supports. Fidelity is therefore **per-format** and **per-capture-mode**. The two
axes are independent: a format can have rich native rendering and still carry
degraded provenance (passive capture), or full provenance and a non-native
overlay (a format with no track-changes concept).

## 1. Per-format capability matrix

| Format | Status | How edits are captured | Native review surface | What you actually get | Limits |
|--------|--------|------------------------|-----------------------|------------------------|--------|
| **`.docx`** | **Available (v0.1)** | active (MCP `changex-mcp`) · passive (`open`/`seal`) · scripted (`changex track`) | **Native Word revisions** (`<w:ins>` / `<w:del>` / `<w:rPrChange>` / `<w:pPrChange>`), author = model id, timestamped | Real accept/reject in Word; `.changex` journal; HTML/file report; `changex view` webserver | Op set: text insert/delete/replace, paragraph insert/delete, style change, **run-format (`format.run`)** and **paragraph move (`node.move`)** — all implemented (see §4). |
| **`.xlsx`** | **Available** | scripted (`changex track`) / programmatic (`changex-core`) | **Non-native overlay**: colored cells + threaded comments + a generated "Changes" audit sheet | `.changex` journal; the overlay written back into the workbook; HTML/file report; `changex view` webserver | xlsx has **no native track-changes**, so review is an annotation overlay, **not** accept/reject-in-place. Op set: `cell.set` / `formula.set` / `row.insert` / `row.delete`. Live MCP + passive `open`/`seal` are docx-only today. |
| **`.csv`** | **Available** | scripted (`changex track`) / programmatic | **Non-native overlay**: unified / side-by-side redline | `.changex` journal; redline projection; HTML/file report; `changex view` webserver | No in-file revision concept at all; review lives entirely in the journal + redline projection. |
| **`.pptx`** | **Available** | scripted (`changex track`) / programmatic | **Non-native overlay**: revision callout shapes + a generated "Revisions" summary slide / notes | `.changex` journal; the overlay written back into the deck; HTML/file report; `changex view` webserver | pptx has **no native track-changes format**; "accept/reject" is reconstructed from the journal, **not** a PowerPoint feature. Op set: `slide.insert` / `slide.delete` / `shape.edit`. |
| **`.md`** | **Available (v0.1.1)** | scripted (`changex track`) / programmatic | **Non-native overlay**: inline HTML redline (`<ins>` / `<del>`) | `.changex` journal; the HTML redline projection; HTML/file report; `changex view` webserver | Markdown has **no native track-changes**; review is the inline HTML redline + journal. Text insert/delete/replace over the parsed block model. |
| **`.doc` (legacy)** | **Available — best-effort (v0.1.1)** | via `.docx` after a LibreOffice headless conversion | **Native Word revisions** (post-conversion, identical to `.docx`) | Same review surfaces as `.docx` once converted | Conversion needs `soffice` (LibreOffice) on PATH and is **lossy for exotic legacy features**; round-trip fidelity is not guaranteed. Treat as best-effort, not authoritative. |

**Read the matrix this way:** `.docx`, `.xlsx`, `.csv`, `.pptx`, and `.md` are all built
and reachable from the CLI today — what differs is the **review surface** and **how edits
are captured**. Only `.docx` has a *native* host-app mechanism (Word revisions) and the
richest capture path (live MCP, passive `open`/`seal`, or scripted `track`); the other
formats review through a **journal + non-native overlay** and are captured today via
scripted `changex track` (or the `changex-core` API), because Excel/CSV/PowerPoint/Markdown
have no native track-changes concept. Legacy `.doc` is ingested by converting it to `.docx`
first (LibreOffice). The journal is equally authoritative across every format.

### Why "non-native overlay" is not a weaker promise where it appears

For docx, "native" means Word itself owns accept/reject. For xlsx/csv/pptx there is
**no equivalent native mechanism**, so ChangeX's overlay (annotations, audit sheet,
summary slide) plus the portable journal *is* the review surface. The journal is
equally authoritative in every case; what differs is whether the host application
can natively resolve the change or whether ChangeX projects the resolution.

## 2. Capture-mode fidelity (active vs passive)

The same journal can be produced two ways, and they are **not** equal in provenance.
(Both the live MCP path and the passive `open`/`seal` path are **docx-only** today; the
other formats are captured with scripted `changex track`, which records fully-shaped ops
just like active capture but without the live agent/turn/prompt provenance an MCP session
supplies.)

| | **Active capture** (MCP) | **Passive capture** (`changex open` / `seal`) |
|---|---|---|
| How ops are recorded | Each MCP `edit` tool call appends one fully-shaped op as it happens | `seal` diffs current vs the stored baseline and **reconstructs** a coarse op stream |
| `agent` (model id) | declared (from `agent_context` at open) or `null` | **`null`** |
| `vendor` | declared or `null` | **`null`** |
| `turn_id` | declared or `null` | **`null`** |
| `prompt_sha256` | declared or `null` | **`null`** |
| `provenance_source` | `declared` (agent fields) / `observed` (server fields) | **`observed`** |
| `rationale` | agent-supplied or `null` | fixed string `"reconstructed by passive diff"` |
| Op granularity | exactly what the model intended | best-effort: paragraph-level alignment, intra-paragraph replace/insert/delete, node insert/delete, style change |
| Replays onto baseline? | yes | yes (verified) |

### Passive mode = degraded provenance (explicit)

When you use `changex open` / `seal` — the "native to any model" path that works
with a local llama.cpp model and a text box, no tool-calling required — ChangeX
**did not observe who made the edit or why.** It only sees before-and-after bytes.
So every reconstructed op carries:

- `agent = null`, `vendor = null`, `turn_id = null`, `prompt_sha256 = null`
- `provenance_source = "observed"`
- `rationale = "reconstructed by passive diff"`

The CLI says this out loud on `seal`. This is **degraded provenance**: you get a
faithful *what-changed* record, but **not** a trustworthy *who/why*. Do not present a
passively-sealed journal as attributing a change to a specific model.

### Passive reconstruction is honest best-effort, not exact intent

`seal` aligns paragraphs with `difflib.SequenceMatcher` and reconstructs ops:

- Pure insertions → `node.insert`; pure deletions → `node.delete`;
  intra-paragraph edits → `text.replace` / `text.insert` / `text.delete`;
  style drift → `style.change`. Each of these reconstructs to the correct op kind.
- **Known coarseness:** when a paragraph is deleted *and* a different one is added in
  the same region, the matcher may align them as a single `text.replace` rather than
  `node.delete` + `node.insert`. The reconstruction still **replays cleanly onto the
  baseline**, but the op *shape* is an approximation of what a human/agent "meant."

All reconstructions replay correctly; the limit is attribution granularity, not
correctness of the resulting document.

## 3. Hash chain = tamper-EVIDENCE, not adversarial integrity

The `.changex` journal is hash-chained: each event's `hash = sha256(prev_hash +
canonical(event))`. Editing any past event invalidates every subsequent hash, and
`changex verify` reports the first broken `seq`.

**What this gives you:** detection of *accidental corruption* and *naive tampering*
(someone hand-edits a line and forgets to recompute the chain).

**What this does NOT give you:** protection against a motivated attacker. Anyone who
controls the `.changex` file can recompute the whole chain after altering it — the
chain is self-describing and unsigned. It is **tamper-evidence, not tamper-proofing**.

Cryptographic signing (which *would* resist an attacker who controls the file) is a
later milestone (M6), not present today. Until then, treat the journal as an audit
aid, not as legal-grade non-repudiation.

### Baseline binding is a separate axis from chain integrity

`changex verify` reports two independent things:

- **chain integrity** (`ok`) — is the hash chain internally consistent?
- **baseline match** (`baseline_match`) — does the on-disk baseline `.docx` still
  hash to the header's `baseline_sha256`?

A missing baseline file is reported as **"not checked,"** not as a failure — absence
of the baseline is not evidence of tampering. Supply `changex verify <journal>
--baseline <docx>` (or store `baseline_uri`) to exercise the baseline axis.

## 4. Operation coverage (nothing reserved as of op-schema v0.3)

The op vocabulary in [CHANGEX_FORMAT.md](CHANGEX_FORMAT.md) froze early so the journal
schema would stay stable as adapters landed. **Every kind in the frozen set now has an
adapter** — the table below is the full implemented vocabulary:

| Op family | Status |
|-----------|--------|
| `text.insert` / `text.delete` / `text.replace` (docx) | **implemented** |
| `node.insert` / `node.delete` (paragraph, docx) | **implemented** |
| `style.change` (docx) | **implemented** |
| `format.run` (bold/italic / run props, docx) | **implemented** (native `w:rPrChange`) — *new in v0.1.1* |
| `node.move` (paragraph move, docx) | **implemented** (tracked delete at source + insert at destination) — *new in v0.1.1* |
| `cell.set` / `formula.set` / `row.insert` / `row.delete` (xlsx/csv) | **implemented** (non-native overlay) |
| `slide.insert` / `slide.delete` / `shape.edit` (pptx) | **implemented** (non-native overlay) |

**As of op-schema v0.3, no op kinds remain reserved** — `format.run` and `node.move` were
the last two, and both now have docx adapters (`format.run` renders a native `w:rPrChange`
run-property revision; `node.move` renders as a tracked delete at the source plus a tracked
insert at the destination — a Word-acceptable move surrogate). The validator still rejects
*unknown* kinds — anything outside the frozen set — with an explicit error rather than
silently mis-handling them, so an unrecognised op in an `ops.json` fails loudly.

## 5. Summary of the honest contract

- **`.docx`, `.xlsx`, `.csv`, `.pptx`, `.md`** are all shipping. `.docx` reviews via
  **native** Word revisions; xlsx/csv/pptx/md review via a **non-native overlay**
  (annotations / audit sheet / summary slide / HTML redline) because those formats have no
  native track-changes. Legacy `.doc` is **best-effort** — converted to `.docx` via
  LibreOffice on ingest.
- **Active (MCP)** capture gives the strongest provenance; **passive (`open`/`seal`)**
  gives faithful *what* but **degraded** *who/why* (null agent/turn/prompt). Both are
  docx-only today; the other formats are captured with scripted `changex track`.
- The hash chain is **tamper-evidence**, not adversarial integrity; signing is later.
- Baseline match is reported separately from chain integrity; a missing baseline is
  "not checked," not a failure.
- **No op kinds remain reserved** as of op-schema v0.3 (`format.run` and `node.move`
  shipped); the validator still refuses *unknown* kinds rather than silently accepting them.

See also: [ARCHITECTURE.md](ARCHITECTURE.md) (design), [ROADMAP.md](ROADMAP.md)
(when PLANNED items land), [INTEGRATION.md](INTEGRATION.md) (cross-vendor wiring),
[CHANGEX_FORMAT.md](CHANGEX_FORMAT.md) (the journal schema).
