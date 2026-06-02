# ChangeX Integration — Native to Any Model

> Status: **how-to.** ChangeX attaches to whatever model you already run — cloud or
> local, tool-capable or not — without per-vendor work. This guide gives copy-paste
> config for each surface and is explicit about **which provenance fields are
> observed vs declared** on each one.

There are exactly **two ways in**, and every model uses one of them:

1. **MCP active-capture** — the model edits *through* ChangeX tools (the
   [`changex-mcp`](../packages/mcp/README.md) server). Provenance is captured at the
   source. Requires an MCP-capable client.
2. **`open` / `seal` passive-capture** — `changex open` snapshots a baseline, the
   model edits the file *however it likes* (chat, script, copy-paste, add-in), and
   `changex seal` reconstructs the journal by diff. **No tool-calling, no SDK, no
   vendor** — works with a local model and a text box. Provenance is degraded
   (see [FIDELITY.md](FIDELITY.md) §2).

Both paths produce the **same `.changex` journal** and feed the **same
visualizations** (`changex review` file/link, `changex view` webserver, the optional
Tauri app). That equivalence is the "native to anything" guarantee.

## 1. Vendor × capture-mode matrix

| Model surface | MCP active-capture | `open`/`seal` passive | Recommended |
|---------------|:------------------:|:---------------------:|-------------|
| **Claude Code** | ✅ | ✅ | MCP |
| **Claude Desktop** | ✅ | ✅ | MCP |
| **Claude (API / Agent SDK)** | ✅ | ✅ | MCP |
| **OpenAI (Agents SDK / Responses)** | ✅ | ✅ | MCP |
| **Gemini (CLI / API)** | ✅ | ✅ | MCP |
| **Cursor** | ✅ | ✅ | MCP |
| **Cline / Continue** | ✅ | ✅ | MCP |
| **LibreChat / Open WebUI** | ✅ (if MCP enabled) | ✅ | MCP if available |
| **Ollama** | ⚠️ only via an MCP-capable client | ✅ | passive |
| **LM Studio** | ⚠️ only via an MCP-capable client | ✅ | passive |
| **llama.cpp / any local runner** | ⚠️ rarely | ✅ | **passive** |
| **Human-in-the-loop / any tool** | — | ✅ | passive |

✅ = first-class · ⚠️ = depends on whether the surrounding client speaks MCP ·
passive always works because it needs only the before/after file.

## 2. Provenance per surface — observed vs declared

ChangeX never fabricates provenance. Each field is labeled by `provenance_source`.

| Field | MCP active | `open`/`seal` passive |
|-------|-----------|-----------------------|
| `ts` (timestamp) | **observed** | **observed** |
| `session_id` | **observed** | **observed** |
| `tool_call_id` | **observed** (transport request id) | n/a (`null`) |
| `client_name` / `client_version` | **observed** (MCP `clientInfo`) | n/a (`null`) |
| `agent` (model id) | **declared** via `agent_context` (or `null`) | **`null`** |
| `vendor` | **declared** (or `null`) | **`null`** |
| `turn_id` | **declared** (or `null`) | **`null`** |
| `prompt_sha256` | **declared** (hashed, never stored verbatim; or `null`) | **`null`** |
| `rationale` | **declared** per edit (or `null`) | fixed `"reconstructed by passive diff"` |

Key honesty point: even over MCP, the transport does **not** carry the user's prompt,
turn, or model id — those are *declared* by the agent (optional, may be `null`), while
only `ts` / `session_id` / `tool_call_id` / `client_*` are *observed* (server-captured,
not trusted from the agent). In passive mode the model id and intent are unknown
entirely, so the attribution fields are `null`. See [FIDELITY.md](FIDELITY.md) §2–3.

## 3. MCP active-capture — copy-paste config

All forms launch the same **stdio** server (`uvx changex-mcp`; with pip, use
`python -m changex_mcp`). Full tool list and the boundary-enforced `edit` contract
live in [`packages/mcp/README.md`](../packages/mcp/README.md).

### Claude Code

```bash
claude mcp add changex -- uvx changex-mcp
```

…or in `~/.claude.json` / project `.mcp.json`:

```json
{ "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
```

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) /
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{ "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
```

### OpenAI (Agents SDK / `MCPServerStdio`)

```python
from agents.mcp import MCPServerStdio

changex = MCPServerStdio(
    params={"command": "uvx", "args": ["changex-mcp"]},
    cache_tools_list=True,
)
# attach: Agent(..., mcp_servers=[changex])
```

For the Responses API hosted-MCP shape, point a stdio bridge at `uvx changex-mcp`.

### Gemini CLI

`~/.gemini/settings.json`:

```json
{ "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
```

### Cursor

`.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global):

```json
{ "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
```

### Cline / Continue

Cline (`cline_mcp_settings.json`) and Continue (`~/.continue/config.json` →
`mcpServers`) use the same stdio block:

```json
{ "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
```

### LibreChat / Open WebUI

Both can register a stdio MCP server. Use the same `command` / `args`
(`uvx changex-mcp`) in their respective `mcpServers` configuration. If the client
build does not expose MCP, fall back to the passive path below — the result is
identical journal + visualizations.

### Declaring your model (so revisions are authored correctly)

MCP cannot read your model id off the wire — declare it once at open:

```jsonc
open_tracked({ "path": "/abs/report.docx",
               "agent_context": { "model": "claude-opus-4-8", "vendor": "anthropic" } })
```

Then revisions and journal events are authored by that model. Omit it and `agent`/
`vendor` stay `null` (honestly unknown), not guessed.

## 4. `open` / `seal` passive-capture — works with ANY model

No MCP, no SDK, no tool-calling. This is the path for Ollama, LM Studio, llama.cpp,
a human editor, or any tool that just reads and writes the file.

```bash
# 1. snapshot the baseline (preserves the exact opened bytes in a sidecar)
changex open report.docx --changex report.changex

# 2. ANY model/tool/human edits report.docx in place — chat, script, add-in, copy back

# 3. reconstruct the attributed journal by diffing current vs the stored baseline
changex seal report.docx --changex report.changex

# 4. verify the chain (+ optionally bind to the baseline) and review
changex verify report.changex --baseline report.docx
changex review report.changex --out review.html        # single-file report / link
changex view   report.changex --doc report.docx        # local webserver
```

### Local-runner recipes (passive)

**Ollama** — generate the edited document however you do today, write it back over
`report.docx` between `open` and `seal`:

```bash
changex open report.docx --changex report.changex
# ... your Ollama pipeline rewrites report.docx ...
changex seal report.docx --changex report.changex
```

**LM Studio / llama.cpp** — identical: the model never touches ChangeX; it only
produces the edited file. `seal` does the attribution-by-diff. Because the model is
unobserved, provenance is **degraded** (`agent`/`vendor`/`turn`/`prompt` = `null`,
`provenance_source = "observed"`) — `seal` prints this explicitly. See
[FIDELITY.md](FIDELITY.md) §2.

> Passive `seal` reconstructs a coarse op stream (paragraph alignment + intra-para
> text edits + node insert/delete + style change) that replays cleanly onto the
> baseline. It is faithful for *what changed*; it does **not** recover *who* or *why*.

## 5. Which path should I use?

- **Tool-capable, you control the client (Claude / OpenAI / Gemini / Cursor / Cline):**
  use **MCP active-capture** — strongest provenance, edits captured as they happen.
- **Local / offline / not tool-capable (Ollama, LM Studio, llama.cpp), or a human,
  or any other tool:** use **`open`/`seal` passive-capture** — same journal and same
  visualizations, with the honest provenance caveat.
- **Embedding in your own agent/pipeline:** `import changex_core` (Tier-3 library).

Either way you get the same `.changex` journal and can render it as a single-file
report (`changex review --out`), a local webserver (`changex view`), native in-file
track changes, or the optional Tauri desktop app.

See also: [ARCHITECTURE.md](ARCHITECTURE.md) · [FIDELITY.md](FIDELITY.md) ·
[`packages/mcp/README.md`](../packages/mcp/README.md) · [ROADMAP.md](ROADMAP.md).
