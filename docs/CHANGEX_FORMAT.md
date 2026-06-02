# The `.changex` journal format

> Status: **draft for review.** The portable, format-independent source of truth
> for everything ChangeX renders.

A `.changex` file is an **append-only JSONL event log** (one JSON object per line)
plus a header line. It is the event-sourced record of every operation an agent
performed on a document, with full provenance. The tracked output document is a
*projection* of this log; the log can be replayed, partially reverted, or verified
independently of any Office format.

## File shape

```
<header>            ← line 1: document + session metadata
<event>             ← line 2..N: one operation each
<event>
...
```

### Header (line 1)

```json
{
  "type": "header",
  "changex_version": "0.1",
  "doc": {
    "filename": "report.docx",
    "format": "docx",
    "baseline_sha256": "…",         // hash of the original document on open
    "baseline_uri": "report.orig.docx"
  },
  "session": {
    "session_id": "uuid",
    "started_at": "2026-06-02T10:00:00Z",
    "capture_mode": "active|passive"
  },
  "prev_hash": null                  // hash chain anchor
}
```

### Event (lines 2..N)

```json
{
  "type": "op",
  "op_id": "uuid",
  "seq": 17,
  "ts": "2026-06-02T10:03:21Z",
  "provenance": {
    "agent": "claude-opus-4-8",      // model id
    "vendor": "anthropic|openai|google|custom",
    "session_id": "uuid",
    "turn_id": "…",                  // conversation turn, if available
    "tool_call_id": "…",             // MCP tool-call id
    "prompt_sha256": "…",            // hash of the instruction that caused the edit
    "rationale": "Tighten the intro per user request"  // optional, agent-supplied
  },
  "target": {
    "node_id": "p:0007",             // stable address in the canonical model
    "kind": "paragraph",
    "path": "/body/sec[1]/p[7]"      // human-readable locator (advisory)
  },
  "op": { … },                       // the operation, see vocabulary below
  "hash": "…",                       // sha256(prev_hash + canonical(this event))
  "prev_hash": "…"
}
```

The `hash`/`prev_hash` chain makes the journal tamper-evident: any edit to a past
event invalidates every subsequent hash.

## Operation vocabulary

Operations are **format-agnostic where possible**, specialized where necessary.
All renderers (native track changes, annotations, HTML redline) consume this same
vocabulary regardless of whether it came from active capture or passive diff.

**Frozen v0.1 op set** (validated by `ops/schema.json`): `text.insert`, `text.delete`,
`text.replace`, `node.insert`, `node.delete`, `style.change`. Everything below marked
*reserved* is **refused by the validator** until its adapter lands.

### Text operations (docx; pptx text frames + csv cells reserved)
Positions are **node-relative and journal-ordered**, never absolute file offsets. The
server validates the supplied `before` against the node's current text and refuses on
mismatch (this is what prevents blind full-node overwrites).
```json
{ "kind": "text.insert",  "node_id": "p:00000007", "before_anchor": "after this", "text": "new clause " }
{ "kind": "text.delete",  "node_id": "p:00000007", "before": "old clause" }
{ "kind": "text.replace", "node_id": "p:00000007", "before": "old", "after": "new" }
{ "kind": "format.run",   "node_id": "p:00000007", "props": { "bold": true }, "before": { "bold": false } }   // reserved
```

### Structural operations
```json
{ "kind": "node.insert", "node_kind": "paragraph", "position": 8, "value": { … } }
{ "kind": "node.delete", "node_id": "p:00000007", "value": { … } }   // value captured for reject/replay
{ "kind": "style.change","node_id": "p:00000007", "style": "Heading 2", "before": "Normal" }
{ "kind": "node.move",   "from": "/…", "to": "/…" }   // reserved
```

### Spreadsheet operations (xlsx, csv) — reserved (planned, M3)
```json
{ "kind": "cell.set",     "sheet": "Q3", "ref": "B7", "before": 100, "after": 125 }
{ "kind": "formula.set",  "sheet": "Q3", "ref": "C7", "before": "=B6", "after": "=B7*1.1" }
{ "kind": "row.insert",   "sheet": "Q3", "at": 7 }
{ "kind": "row.delete",   "sheet": "Q3", "at": 7, "value": [ … ] }
```

### Slide operations (pptx) — reserved (planned, M4)
```json
{ "kind": "slide.insert", "at": 3, "value": { … } }
{ "kind": "slide.delete", "at": 3, "value": { … } }
{ "kind": "shape.edit",   "slide": 2, "shape_id": "…", "op": { … } }  // nested text/format op
```

## Stable node addressing

`node_id` is **opaque and edit-invariant** so that `accept`/`reject` and replay are
deterministic. Strategy (as implemented):

1. **Primary (docx):** reuse Word's native `w14:paraId` for paragraphs (Word preserves
   it across edits); mint a monotonic counter id for any node lacking one and inject a
   `w:bookmark` carrier the renderer strips on accept-all. The `node_id`↔carrier map is
   persisted in the `.changex` header.
2. **Fallback anchor only:** a content+structure fingerprint `{paraId, char-range,
   normalized-text, sibling-context}` is used *solely* for fuzzy re-resolution when the
   sidecar is lost or after out-of-band edits, emitting a `rebind` event with a
   confidence score. It is **never** the primary key — content hashes both collide
   (duplicate paragraphs/cells) and mutate on the very edits ChangeX tracks.
3. **Spreadsheet/csv (planned):** natural keys (`sheet!cellref`) plus a stored `rowId`
   so a cell follows its row under row insert.

## Projections

| Projection | Built by | Output |
|------------|----------|--------|
| Native tracked document | `render.<format>` | `.docx` revisions / `.xlsx` annotations / `.pptx` overlay |
| HTML/markdown redline | `render.html` | review report for CLI + viewer |
| Provenance timeline | viewer | chronological, filterable by model/turn |
| Verification | `journal.verify` | hash-chain integrity + baseline match |

## Design invariants

- **Reversibility:** every destructive op records the prior `value`/`before` so it
  can be rejected or replayed without the original file.
- **Idempotent replay:** replaying the full journal onto the baseline reproduces the
  saved document byte-for-meaning (not necessarily byte-for-byte).
- **Format independence:** a `.changex` is meaningful even if the document is lost,
  as long as the baseline hash/uri is available.
