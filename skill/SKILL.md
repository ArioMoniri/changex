---
name: changex
description: >-
  Track, attribute, and review AI document edits with provenance. Use this skill
  whenever you need to apply edits to a .docx as native Word track-changes (real
  w:ins/w:del revisions authored by the model), produce a portable .changex
  provenance journal, verify that journal's tamper-evident hash chain, or render
  an HTML/markdown redline of "what changed, where, why, and by whom". Triggers on
  requests like "track these edits in the Word doc", "make changes with track
  changes on", "show me a redline of the AI's edits", "verify the change journal",
  or "review the .changex file".
---

# ChangeX — provenance-first document edit tracking

ChangeX wraps the `changex-core` CLI so you can apply semantic edits to a `.docx`
as **native Word revisions** while emitting a portable, hash-chained `.changex`
provenance journal. Word renders the real accept/reject; the `.changex` journal
answers *what changed, where, why, and by whom* and verifies/replays
independently of the file.

This skill drives the `changex` CLI directly. No MCP client is required (for an
agent-native flow over MCP, point your client at the `changex-mcp` server
instead — see `docs/INTEGRATION.md`).

## When to use

- Apply a set of edits to a `.docx` and get back a tracked Word file + a `.changex` journal.
- Verify a `.changex` hash chain (tamper-evidence for accidental corruption / naive edits).
- Render a redline review (HTML or markdown) of a session's changes with provenance.

## Setup (once)

The CLI lives in `packages/core`. Install it into a virtual environment:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e packages/core          # provides the `changex` console script
changex --help
```

## The three commands

### 1. `track` — apply edits as native revisions

Author an ops file (a JSON **array** of op dicts), then run `track`:

```bash
changex track in.docx ops.json \
  --out tracked.docx \
  --changex session.changex \
  --author claude-opus-4-8
```

- `tracked.docx` — open in Word: edits appear as accept/reject revisions authored by `--author`.
- `session.changex` — the portable provenance journal (JSONL: one header line + one event per op).

### 2. `verify` — check the hash chain

```bash
changex verify session.changex
# OK: session.changex verifies (5 ops)   (rc 0)
# FAIL: chain broken at seq=N ...         (rc 1)
```

### 3. `review` — render a redline

```bash
changex review session.changex --format html     --out review.html
changex review session.changex --format markdown                    # to stdout
```

## Op vocabulary (frozen v0.1, docx-only)

Each entry in `ops.json` is one op dict. Use the **smallest** edit that expresses
the intent — do NOT delete-and-reinsert a whole paragraph for a small wording
change. The `before` string must match the current node text exactly; the tool
refuses on mismatch and rejects oversized ops (>50% of a node) with a
`split_required` error.

| `kind`          | required keys                          | meaning                              |
| --------------- | -------------------------------------- | ------------------------------------ |
| `text.replace`  | `node_id`, `before`, `after`           | replace a substring in a paragraph   |
| `text.insert`   | `node_id`, `text` (`before_anchor?`)   | insert text (after an anchor)        |
| `text.delete`   | `node_id`, `before`                    | delete a substring                   |
| `node.insert`   | `node_kind`, `position`, `value`       | insert a new paragraph               |
| `node.delete`   | `node_id`, `value`                     | delete a paragraph                   |
| `style.change`  | `node_id`, `style`, `before`           | change a paragraph style             |

An optional top-level `"rationale"` key on any op is recorded as provenance (not
op payload). `node_id`s are opaque and edit-invariant (docx paragraphs reuse
Word's native `w14:paraId`); discover them from a prior `review` or the MCP
`get_outline` tool.

`format.run` and `node.move`, and all xlsx/pptx/csv ops, are **reserved and not
yet implemented** — the CLI rejects them.

### Example `ops.json`

```json
[
  { "kind": "text.replace", "node_id": "p:00000002", "before": "quick", "after": "swift" },
  { "kind": "style.change", "node_id": "p:00000001", "style": "Heading 1", "before": "Normal", "rationale": "promote heading" },
  { "kind": "text.insert", "node_id": "p:00000002", "before_anchor": "fox", "text": " (Vulpes vulpes)" }
]
```

## Typical flow

1. `changex review old.changex --format markdown` (if a journal exists) or open the
   doc to discover the `node_id`s you want to edit.
2. Write `ops.json` with the smallest ops that express the intent.
3. `changex track in.docx ops.json --out tracked.docx --changex session.changex --author <model-id>`.
4. `changex verify session.changex` and `changex review session.changex --out review.html`.
5. Hand the user `tracked.docx` (review in Word) and `review.html` (review without Word).

## Notes & honest limits

- Provenance: `ts`, `session_id`, and `author` are captured; `agent`/`vendor`/`rationale`
  are declared (labeled `provenance_source`), never fabricated.
- The hash chain gives tamper-**evidence** for accidental corruption and naive
  tampering only — not adversarial integrity (an attacker controlling the file
  can recompute the chain). Signing is deferred.
- Passive/out-of-band edits are surfaced as a baseline-mismatch **warning**, not
  reconstructed into ops.
- The desktop review app (Tauri) lives in `packages/viewer` and is an optional
  visual surface over the same `.changex` journal + HTML redline.
