# changex-mcp

The **ChangeX MCP server**: an MCP client (Claude Code/Desktop, OpenAI, Gemini
CLI, …) opens a `.docx`, makes small intent-named edits, and gets back

1. a **Word file with native accept/reject revisions** authored by the model, and
2. a portable, hash-chained **`.changex` provenance journal** recording what
   changed, where, and (where known) why and by whom.

It is a thin [FastMCP](https://github.com/modelcontextprotocol/python-sdk) (stdio)
wrapper around the [`changex-core`](../core) spine. The server holds in-process,
single-session-per-handle state; the journal is flushed to disk on **every** edit,
and the edit sequence number is **server-assigned** so concurrent tool calls in one
turn stay ordered and race-free.

## Install / run

```bash
# zero-clone (recommended for end users):
uvx changex-mcp

# from this monorepo (dev): installs core from the workspace
uv sync
uv run changex-mcp

# or with pip:
pip install changex-mcp        # pulls in changex-core
python -m changex_mcp          # identical to the `changex-mcp` script
```

All three forms start the same **stdio** server. Setup is under 10 minutes: install,
drop one of the config blocks below into your client, restart the client.

## Remote HTTP transport (connector-URL clients)

Some clients don't spawn a local process — they connect to an MCP server over a
**URL**. claude.ai *custom connectors* and ChatGPT *app connectors* are both
URL-based. For those, run the same server over **Streamable HTTP** instead of stdio:

```bash
# loopback only (default host 127.0.0.1, port 9000, path /mcp) — no token needed
changex-mcp --http
# → serves http://127.0.0.1:9000/mcp

# pick host / port / path
changex-mcp --http --host 127.0.0.1 --port 9000 --path /mcp
```

Everything is also configurable by environment variable (CLI flags win over env):

| Env var | Meaning | Default |
|---------|---------|---------|
| `CHANGEX_MCP_TRANSPORT` | `stdio` \| `http` \| `sse` | `stdio` |
| `CHANGEX_MCP_HOST` | HTTP bind host | `127.0.0.1` |
| `CHANGEX_MCP_PORT` | HTTP bind port | `9000` |
| `CHANGEX_MCP_PATH` | HTTP endpoint path | `/mcp` |
| `CHANGEX_MCP_TOKEN` | Bearer token (see security) | *(none)* |
| `CHANGEX_MCP_PUBLIC` | `1` to acknowledge a non-loopback bind | *(off)* |

The HTTP deps (`starlette` + `uvicorn`) ship with the SDK's `cli` extra; if you
installed a minimal wheel, add them with `pip install "changex-mcp[http]"`.

### Connector URL shape

```
http://<host>:<port><path>          e.g.  http://127.0.0.1:9000/mcp
```

That URL is exactly what you paste into a claude.ai custom connector or a ChatGPT
app connector. Authenticate with an `Authorization: Bearer <CHANGEX_MCP_TOKEN>`
header (required for any non-loopback bind; optional but recommended on loopback).

### Security: this server edits local files

Because the tools write `.docx`/`.changex` files on the host, the bind policy is
**fail-closed**:

- **Default is loopback** (`127.0.0.1`). A loopback bind needs no token.
- **Binding to a non-loopback host or `0.0.0.0` is refused** unless you supply
  **both**:
  1. the explicit `--public` flag (or `CHANGEX_MCP_PUBLIC=1`), **and**
  2. a bearer token in `CHANGEX_MCP_TOKEN`.

  A public bind without a token aborts with a clear warning rather than silently
  exposing file-editing tools to the network:

  ```bash
  CHANGEX_MCP_TOKEN=$(openssl rand -hex 32) changex-mcp --http --host 0.0.0.0 --public
  ```

To reach a loopback HTTP server from a cloud client, put it behind a TLS reverse
proxy / tunnel and keep the bearer token on — never expose the raw port.

## Tools

| Tool | Purpose |
|------|---------|
| `open_tracked(path, agent_context?, author?)` | Open a `.docx`; returns `{handle, summary, baseline_sha256, session_id}`. Pass `agent_context={"model","vendor"}` so revisions are authored by your model. |
| `get_outline(handle, cursor?, limit?)` | Bounded, paginated paragraph list → discover `node_id`s. Returns `{nodes:[{node_id,kind,preview,style}], next_cursor, total}`. |
| `edit(handle, op, node_id, …)` | One small tracked edit. `op` ∈ `replace_text` / `insert_text_after` / `delete_text` / `set_paragraph_style`. Returns `{op_id, seq, node_id, provenance_source}`. |
| `reject(handle, op_id)` | Reject a change by `op_id`: the op is non-destructively reverted (the rejection itself is audited) and excluded from the next `save_tracked`, so its revision is genuinely absent from the saved `.docx`. Returns `{op_id, status, reverted, active_ops, verified}`. |
| `accept(handle, op_id)` | Accept (un-reject) a previously rejected `op_id` so its revision is kept and reappears on the next `save_tracked`. Returns `{op_id, status, reverted, active_ops, verified}`. |
| `save_tracked(handle, out)` | Write the native-revisions `.docx` as a pure projection of the journal's **non-reverted** events; returns `{tracked_path, changex_path, ops, verified}` (`ops` = active op count). |
| `get_changes(handle)` | The structured provenance journal: `{session_id, events:[…], count, verified}`. |
| `render_review(handle, fmt?)` | Human-readable redline; `fmt` ∈ `html` / `markdown`. Returns `{format, report}`. |

### The `edit` contract (boundary-enforced, not just prompted)

`edit` is intent-dispatched on `op`; supply only that intent's fields:

```
replace_text        → node_id, before (exact current text), after
insert_text_after   → node_id, anchor (exact text to insert after), text
delete_text         → node_id, before (exact text to delete)
set_paragraph_style → node_id, style (new), before (current style name)
```

The server **refuses**:

- **`before_mismatch`** — `before`/`anchor` must match the node's *current* text
  exactly. This kills blind full-node overwrites.
- **`split_required`** — an op rewriting >50% of a paragraph is rejected with a
  structured message instructing the model to split it into smaller `replace_text`
  edits. The error *is* the prompt.

Errors are returned as `{"error": "<code>", "detail": "<message>"}`.

## Provenance: observed vs declared (honest)

MCP tool calls do **not** carry the user's prompt, conversation turn, model id, or
vendor. So ChangeX splits provenance and labels each event with
`provenance_source`:

- **observed** (server-captured, not trusted from the agent): `ts`, `session_id`,
  `tool_call_id` (transport request id), and `client_name` / `client_version` from
  the MCP `clientInfo` handshake.
- **declared** (agent-supplied, optional, may be `null`): `agent` (model id) and
  `vendor` — captured **once** at `open_tracked` via `agent_context`; plus optional
  per-edit `rationale`, `prompt` (hashed to `prompt_sha256`, never stored verbatim),
  and `turn_id`.

## MCP client configuration (copy-paste)

> These use `uvx changex-mcp`. If you installed with pip, replace the command with
> `python` and args with `["-m", "changex_mcp"]`.

### Claude Code

```bash
claude mcp add changex -- uvx changex-mcp
```

…or add to `~/.claude.json` (or the project `.mcp.json`):

```json
{
  "mcpServers": {
    "changex": {
      "command": "uvx",
      "args": ["changex-mcp"]
    }
  }
}
```

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) /
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "changex": {
      "command": "uvx",
      "args": ["changex-mcp"]
    }
  }
}
```

### OpenAI (Agents SDK / `MCPServerStdio`)

```python
from agents.mcp import MCPServerStdio

changex = MCPServerStdio(
    params={
        "command": "uvx",
        "args": ["changex-mcp"],
    },
    cache_tools_list=True,
)
# then attach `changex` to your Agent(..., mcp_servers=[changex])
```

For the OpenAI Responses API hosted-MCP shape, point a stdio bridge at
`uvx changex-mcp`.

### Gemini CLI

`~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "changex": {
      "command": "uvx",
      "args": ["changex-mcp"]
    }
  }
}
```

### claude.ai custom connector (remote, URL-based)

Custom connectors dial a **URL**, so run the HTTP transport first:

```bash
export CHANGEX_MCP_TOKEN=$(openssl rand -hex 32)
changex-mcp --http            # → http://127.0.0.1:9000/mcp
```

Then in claude.ai → **Settings → Connectors → Add custom connector**:

- **URL**: `http://127.0.0.1:9000/mcp` (or your TLS-tunneled public URL)
- **Authentication**: header `Authorization: Bearer <CHANGEX_MCP_TOKEN>`

A cloud client can't reach `127.0.0.1` on your laptop directly — front the
loopback server with a TLS tunnel/reverse proxy and use that HTTPS URL, keeping
the bearer token on. Any non-loopback bind **requires** `--public` + the token.

### ChatGPT app connector (remote, URL-based)

Same server, same URL shape. Start it:

```bash
export CHANGEX_MCP_TOKEN=$(openssl rand -hex 32)
changex-mcp --http --host 127.0.0.1 --port 9000 --path /mcp
```

In ChatGPT → **Settings → Connectors / Apps → Add** (developer mode for a custom
MCP app):

- **MCP server URL**: `https://<your-tunnel-host>/mcp` (point your tunnel at the
  loopback `http://127.0.0.1:9000/mcp`)
- **Auth**: bearer token = `CHANGEX_MCP_TOKEN`

## End-to-end example (what the model calls)

```jsonc
// 1. open
open_tracked({ "path": "/abs/report.docx",
               "agent_context": { "model": "claude-opus-4-8", "vendor": "anthropic" } })
// → { "handle": "ab12…", "summary": {…}, "baseline_sha256": "…", "session_id": "…" }

// 2. discover node_ids
get_outline({ "handle": "ab12…" })
// → { "nodes": [ { "node_id": "p:00000002", "preview": "The quick brown fox…" } ], … }

// 3. smallest edits
edit({ "handle": "ab12…", "op": "replace_text",
       "node_id": "p:00000002", "before": "quick", "after": "swift",
       "rationale": "tighter wording" })
edit({ "handle": "ab12…", "op": "set_paragraph_style",
       "node_id": "p:00000001", "before": "Normal", "style": "Heading 1" })

// 4. review: reject (drop) or accept (restore) individual changes by op_id
reject({ "handle": "ab12…", "op_id": "…op-id-of-edit-2…" })
// → { "op_id": "…", "status": "rejected", "reverted": true, "active_ops": 1, "verified": true }
accept({ "handle": "ab12…", "op_id": "…op-id-of-edit-2…" })
// → { "op_id": "…", "status": "accepted", "reverted": false, "active_ops": 2, "verified": true }

// 5. save → native Word revisions + .changex (only non-reverted ops are rendered)
save_tracked({ "handle": "ab12…", "out": "/abs/report.tracked.docx" })
// → { "tracked_path": "…", "changex_path": "…/report.changex", "ops": 2, "verified": true }

// 6. review / audit
render_review({ "handle": "ab12…", "fmt": "markdown" })
get_changes({ "handle": "ab12…" })
```

## Notes / limits

- **docx only** in v0.1 (the frozen op set: text insert/delete/replace, paragraph
  insert/delete, style change). xlsx/pptx/csv and `format.run` / `node.move` are
  reserved for later versions.
- **Single-session per document.** Opening the same file twice in one server is
  refused rather than left undefined.
- The hash chain is **tamper-evidence** for accidental corruption / naive tampering,
  not adversarial integrity — signing is a later milestone.
