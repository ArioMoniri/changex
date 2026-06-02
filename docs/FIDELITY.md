# ChangeX Fidelity & Limits

> Status: **honest capability statement.** This is the document reviewers asked
> for: a per-format capability matrix and the explicit limits, with nothing
> oversold. If a row says PLANNED, the code path does not exist yet. If a guarantee
> is qualified, the qualification is load-bearing — read it.

ChangeX renders an operation journal onto whatever review surface a format
supports. Fidelity is therefore **per-format** and **per-capture-mode**. The two
axes are independent: a format can have rich native rendering and still carry
degraded provenance (passive capture), or full provenance and a non-native
overlay (a format with no track-changes concept).

## 1. Per-format capability matrix

| Format | Status | Capture | Native review surface | What you actually get | Limits |
|--------|--------|---------|-----------------------|------------------------|--------|
| **`.docx`** | **Available (v0.1)** | active (MCP) + passive (`open`/`seal`) | **Native Word revisions** (`<w:ins>` / `<w:del>`), author = model id, timestamped | Real accept/reject in Word; `.changex` journal; HTML/file report; `changex view` webserver | Frozen op set (text insert/delete/replace, paragraph insert/delete, style change). `format.run` / `node.move` reserved (see §4). |
| **`.xlsx`** | **PLANNED** (M3) | active + passive (designed) | **Non-native overlay**: colored cells + threaded comments + a generated "Changes" audit sheet | — (journal + overlay are designed, not built) | xlsx has **no robust native track-changes**; review is an annotation overlay, not accept/reject-in-place. |
| **`.csv`** | **PLANNED** (M3) | active + passive (designed) | **Non-native overlay**: unified / side-by-side redline | — (designed, not built) | No in-file revision concept at all; review lives entirely in the journal + redline projection. |
| **`.pptx`** | **PLANNED** (M4) | active + passive (designed) | **Non-native overlay**: revision callout shapes + a generated "Revisions" summary slide / notes | — (designed, not built) | pptx has **no native track-changes format**; "accept/reject" is reconstructed from the journal, not a PowerPoint feature. |
| **`.doc` (legacy)** | **Experimental** | passive only (realistically) | via docx after conversion | Best-effort: LibreOffice-headless converts `.doc` → `.docx` on ingest, tracked in docx, optionally converted back | Conversion is lossy for exotic legacy features; round-trip fidelity is not guaranteed. Treat as best-effort, not authoritative. |

**Read the matrix this way:** only `.docx` is built today. Everything else is a
committed design with a reserved op vocabulary and a named review surface — but the
adapter/renderer is not implemented, so do not promise it to a user as working.

### Why "non-native overlay" is not a weaker promise where it appears

For docx, "native" means Word itself owns accept/reject. For xlsx/csv/pptx there is
**no equivalent native mechanism**, so ChangeX's overlay (annotations, audit sheet,
summary slide) plus the portable journal *is* the review surface. The journal is
equally authoritative in every case; what differs is whether the host application
can natively resolve the change or whether ChangeX projects the resolution.

## 2. Capture-mode fidelity (active vs passive)

The same journal can be produced two ways, and they are **not** equal in provenance.

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

## 4. Reserved / unimplemented operations

The op vocabulary in [CHANGEX_FORMAT.md](CHANGEX_FORMAT.md) is deliberately broader
than what is implemented, so the journal schema is stable as formats land. Today:

| Op family | Status |
|-----------|--------|
| `text.insert` / `text.delete` / `text.replace` (docx) | **implemented** |
| `node.insert` / `node.delete` (paragraph, docx) | **implemented** |
| `style.change` (docx) | **implemented** |
| `format.run` (bold/italic/run props) | **reserved — not implemented** (CLI rejects) |
| `node.move` | **reserved — not implemented** (CLI rejects) |
| `cell.set` / `formula.set` / `row.insert` / `row.delete` (xlsx/csv) | **reserved — not implemented** |
| `slide.insert` / `slide.delete` / `shape.edit` (pptx) | **reserved — not implemented** |

Reserved ops are present in the spec so downstream tooling can be written against the
final shape, but the active CLI and MCP server **refuse** them rather than silently
mis-handling them. If you author one in an `ops.json`, you get an explicit rejection.

## 5. Summary of the honest contract

- Only **`.docx`** is shipping. xlsx/csv/pptx are PLANNED with a non-native overlay
  design; legacy `.doc` is experimental via conversion.
- **Active (MCP)** capture gives the strongest provenance; **passive (`open`/`seal`)**
  gives faithful *what* but **degraded** *who/why* (null agent/turn/prompt).
- The hash chain is **tamper-evidence**, not adversarial integrity; signing is later.
- Baseline match is reported separately from chain integrity; a missing baseline is
  "not checked," not a failure.
- A chunk of the op vocabulary is **reserved and refused**, not silently accepted.

See also: [ARCHITECTURE.md](ARCHITECTURE.md) (design), [ROADMAP.md](ROADMAP.md)
(when PLANNED items land), [INTEGRATION.md](INTEGRATION.md) (cross-vendor wiring),
[CHANGEX_FORMAT.md](CHANGEX_FORMAT.md) (the journal schema).
