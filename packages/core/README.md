# changex-core

Core of **ChangeX** — the provenance-first edit-tracking spine (roadmap M0).

This package contains, with **no network access** and **no MCP dependency**:

- **`changex_core.model`** — a canonical, addressable document-node tree whose
  `node_id` is an *opaque, edit-invariant* identifier (NOT a content hash). For
  docx paragraphs it reuses Word's native `w14:paraId`; for nodes lacking a native
  id it mints a monotonic per-session counter. A content+position fingerprint is
  demoted to a *fallback rebind anchor* used only for fuzzy re-resolution.
- **`changex_core.ops`** — the frozen **v0.1 op vocabulary** (docx-only):
  `text.insert`, `text.delete`, `text.replace`, `node.insert`, `node.delete`,
  `style.change`. Offsets are *node-relative* and *seq-ordered*; `before` substrings
  are validated against current node content.
- **`changex_core.journal`** — the append-only JSONL `.changex` journal with an
  RFC 8785 (JCS) canonicalized **sha256 hash chain**, plus `append`, `read`,
  `replay`, `verify`, and `revert`.
- **`changex_core.adapters`** — the `DocumentAdapter` contract and the **docx
  adapter** that loads a `.docx`, applies the v0.1 ops, and renders **native Word
  revisions** (`<w:ins>` / `<w:del>` / `<w:delText>` / `<w:pPrChange>`) with
  centrally-allocated unique `w:id`, `w:author = <model name>`, and `w:date`.
- **`changex_core.render`** — an HTML/markdown redline projection of the journal.
- **`changex_core.baseline`** — a baseline snapshot + out-of-band mismatch warning.
- **`changex_core.cli`** — a thin CLI (`changex track / review / verify`) that
  exercises the spine for the M0 script-based acceptance test.

## Threat model (hash chain)

The hash chain gives **tamper-evidence** for accidental corruption and naive
tampering only. An attacker who controls the `.changex` can recompute the whole
chain. Adversarial integrity requires out-of-band storage or signing (deferred to
M6).
