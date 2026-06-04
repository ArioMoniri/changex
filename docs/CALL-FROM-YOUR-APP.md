# Call ChangeX from your app — copy-paste recipes

> Status: **how-to.** This is the definitive "wire ChangeX into your LLM app" guide.
> Every flag, URL, endpoint, and file below is real and shipping. For the *why* (the
> two capture modes and the per-surface provenance honesty), read
> [INTEGRATION.md](INTEGRATION.md). For the *what changed* limits, read
> [FIDELITY.md](FIDELITY.md).

There are three ways ChangeX plugs into an app, and each app below uses one:

1. **MCP — stdio** (`uvx changex-mcp`): the client spawns a local process. This is the
   primary path for desktop/CLI clients (Claude Desktop, Claude Code, Cursor, Cline,
   Gemini CLI, OpenAI Agents SDK).
2. **MCP — remote HTTP** (`changex-mcp --http`): the client dials a **URL**. This is the
   path for cloud, connector-URL clients (claude.ai custom connectors, ChatGPT app
   connectors).
3. **REST / function tools** (`changex-api`, schemas in [`integrations/`](../integrations/)):
   plain HTTP over the same core, for ChatGPT custom-GPT **Actions**, OpenAI/Gemini
   function calling, or any client that can't speak MCP.

> 💡 **Shortcut — `changex connect <app>`.** Instead of hand-editing the JSON below, run
> `changex connect claude-desktop` / `cursor` / `gemini` (it merges the entry, backs the
> file up, and uses the absolute binary path), or `changex connect chatgpt` / `claude-web`
> to print the remote-connector runbook with a fresh token. Run `changex connect` to list
> targets. The recipes below are the same wiring done by hand.

When none of those fit (a fully offline, no-tool-calling model, or a human), use the
**passive `changex open` / `seal`** path — it works with anything that reads and writes
the file. Passive capture is faithful for *what changed* but has **degraded provenance**
(who/why is `null`); see [FIDELITY.md](FIDELITY.md) §2.

## Quick pick

| Your app | Use this | Recipe |
|----------|----------|--------|
| **Claude Desktop / Claude Code** | MCP stdio | [↓](#claude-desktop--claude-code-mcp-stdio) |
| **claude.ai** (web) | MCP remote HTTP (custom connector) | [↓](#claudeai-custom-connector-mcp-remote-http) |
| **ChatGPT** (app connector) | MCP remote HTTP | [↓](#chatgpt-app-connector-mcp-remote-http) |
| **ChatGPT** (custom GPT Action) | REST `/openapi.json` | [↓](#chatgpt-custom-gpt-action-rest-openapijson) |
| **OpenAI Agents / Responses** | MCP (stdio or HTTP) or function tools | [↓](#openai-agents--responses) |
| **Gemini** (CLI) | MCP stdio | [↓](#gemini) |
| **Gemini** (API) | function declarations | [↓](#gemini) |
| **Cursor / Cline** | MCP stdio (`.cursor/mcp.json`) | [↓](#cursor--cline-mcp-stdio) |
| **Ollama / LM Studio** | MCP if supported, else passive + REST | [↓](#ollama--lm-studio-local) |

---

## Claude Desktop / Claude Code (MCP stdio)

One line for Claude Code:

```bash
claude mcp add changex -- uvx changex-mcp
```

Or drop the stdio block into the client config. **Claude Code:** `~/.claude.json` or the
project `.mcp.json`. **Claude Desktop:**
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) /
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{ "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
```

Installed with pip instead of uv? Use `"command": "python", "args": ["-m", "changex_mcp"]`.

Then tell the agent to open and edit a doc — it calls `open_tracked` → `edit` →
`save_tracked`. Declare your model once so the Word revisions are authored correctly:

```jsonc
open_tracked({ "path": "/abs/report.docx",
               "agent_context": { "model": "claude-opus-4-8", "vendor": "anthropic" } })
```

Full tool contract: [`packages/mcp/README.md`](../packages/mcp/README.md).

## claude.ai custom connector (MCP remote HTTP)

claude.ai dials a **URL**, so run the server over Streamable HTTP rather than stdio.
Because the tools write files on the host, mint a bearer token:

```bash
export CHANGEX_MCP_TOKEN=$(openssl rand -hex 32)
changex-mcp --http            # → serves http://127.0.0.1:9000/mcp
```

Then in claude.ai → **Settings → Connectors → Add custom connector**:

- **URL**: `http://127.0.0.1:9000/mcp` (or your TLS-tunneled public URL — see note)
- **Authentication**: header `Authorization: Bearer <CHANGEX_MCP_TOKEN>`

**Localhost vs public — read this.** A cloud client cannot reach `127.0.0.1` on your
laptop. Front the loopback server with a TLS tunnel / reverse proxy and paste that
**HTTPS** URL, keeping the bearer token on. The server's bind policy is **fail-closed**:
loopback (`127.0.0.1`) needs no token, but binding `0.0.0.0` or any non-loopback host is
**refused** unless you pass **both** `--public` (or `CHANGEX_MCP_PUBLIC=1`) **and** a
`CHANGEX_MCP_TOKEN`:

```bash
CHANGEX_MCP_TOKEN=$(openssl rand -hex 32) changex-mcp --http --host 0.0.0.0 --public
```

A public bind without a token aborts with a clear warning rather than silently exposing
file-editing tools to the network.

## ChatGPT app connector (MCP remote HTTP)

Same server, same URL shape as claude.ai. Start it:

```bash
export CHANGEX_MCP_TOKEN=$(openssl rand -hex 32)
changex-mcp --http --host 127.0.0.1 --port 9000 --path /mcp
```

In ChatGPT → **Settings → Connectors / Apps → Add** (developer mode for a custom MCP app):

- **MCP server URL**: `https://<your-tunnel-host>/mcp` (point your tunnel at the loopback
  `http://127.0.0.1:9000/mcp`)
- **Auth**: bearer token = `CHANGEX_MCP_TOKEN`

The same localhost-vs-public security note above applies: never expose the raw `9000`
port; tunnel it over TLS and keep the token on.

## ChatGPT custom GPT Action (REST `/openapi.json`)

If you'd rather give a **custom GPT** an **Action** than wire an MCP connector, point the
Action at ChangeX's OpenAPI schema. Run the REST API:

```bash
uv sync && changex-api            # or: python -m changex_api  → binds 127.0.0.1:8000
```

FastAPI auto-serves the schema at **`http://127.0.0.1:8000/openapi.json`** — that file
*is* the Action schema. In the GPT editor → **Configure → Actions → Create new action →
Import from URL**, paste that URL (or upload the static copy at
[`integrations/openapi.json`](../integrations/openapi.json) if your laptop isn't
reachable from ChatGPT — front it with a tunnel for live calls). Endpoints
(`operationId`s):

| Method & path | operationId |
|---|---|
| `POST /sessions` | `openTracked` |
| `GET  /sessions/{handle}/outline` | `getOutline` |
| `POST /sessions/{handle}/edit` | `editSession` |
| `POST /sessions/{handle}/save` | `saveSession` |
| `GET  /sessions/{handle}/changes` | `getChanges` |
| `POST /open` | `passiveOpen` |
| `POST /seal` | `passiveSeal` |
| `POST /report` | `renderReport` |
| `GET  /healthz` | `healthz` |

Auth: bind is `127.0.0.1` by default (no token). A non-local bind is **refused** unless
`CHANGEX_API_TOKEN` is set; when it is, every non-`/healthz` route requires
`Authorization: Bearer <token>`:

```bash
CHANGEX_API_TOKEN=$(openssl rand -hex 32) changex-api --host 0.0.0.0 --port 9000
```

## OpenAI (Agents / Responses)

**Agents SDK — MCP stdio** (recommended; provenance captured at the source):

```python
from agents.mcp import MCPServerStdio

changex = MCPServerStdio(
    params={"command": "uvx", "args": ["changex-mcp"]},
    cache_tools_list=True,
)
# attach: Agent(..., mcp_servers=[changex])
```

For the **Responses API** hosted-MCP shape, point a stdio bridge at `uvx changex-mcp`, or
serve `changex-mcp --http` and give the hosted-MCP tool the URL +
`Authorization: Bearer <CHANGEX_MCP_TOKEN>` header.

**Function tools (no MCP).** If you'd rather hand-register tools, load
[`integrations/openai-functions.json`](../integrations/openai-functions.json) (OpenAI
`tools` format — 8 functions: `openTracked`, `getOutline`, `editSession`, `saveSession`,
`getChanges`, `passiveOpen`, `passiveSeal`, `renderReport`) and route each call to the
matching `changex-api` endpoint:

```python
import json, openai
tools = json.load(open("integrations/openai-functions.json"))["tools"]
resp = openai.responses.create(model="gpt-4o", input=msgs, tools=tools)
# dispatch tool calls → changex-api (e.g. openTracked → POST http://127.0.0.1:8000/sessions)
```

## Gemini

**CLI — MCP stdio.** Add the stdio block to `~/.gemini/settings.json`:

```json
{ "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
```

**API — function declarations.** Load
[`integrations/gemini-functions.json`](../integrations/gemini-functions.json) (Gemini
`functionDeclarations` format, same 8 functions) and dispatch each call to the matching
`changex-api` endpoint:

```python
import json, google.generativeai as genai
fns = json.load(open("integrations/gemini-functions.json"))["functionDeclarations"]
model = genai.GenerativeModel("gemini-1.5-pro", tools=[{"function_declarations": fns}])
# on a functionCall, call the matching changex-api route and return the result
```

## Cursor / Cline (MCP stdio)

**Cursor** — `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global):

```json
{ "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
```

**Cline** — same block in `cline_mcp_settings.json` (Cline → MCP Servers → Configure).
Both spawn the local stdio server; no token or URL needed.

## Ollama / LM Studio (local)

**If your client supports MCP**, register the same stdio block it uses for other servers:

```json
{ "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
```

(LM Studio exposes MCP in recent builds; Ollama itself does not call tools — drive it
from an MCP-capable wrapper, or use the passive path below.)

**If it can't speak MCP** — the universal fallback. Snapshot a baseline, let the model
edit the file *however it likes*, then reconstruct the journal by diff. No SDK, no
tool-calling:

```bash
changex open  report.docx --changex report.changex   # snapshot the baseline
# … your Ollama / LM Studio pipeline rewrites report.docx in place …
changex seal  report.docx --changex report.changex   # reconstruct the journal by diff
changex review report.changex --out review.html       # single-file report
```

Provenance is honestly **degraded** here: `seal` recovers *what* changed but not *who/why*
(`agent`/`vendor`/`turn`/`prompt` = `null`), and prints that explicitly. See
[FIDELITY.md](FIDELITY.md) §2.

**Or drive the REST API** from a local script (no MCP, full attribution if you declare it):
run `changex-api` (binds `127.0.0.1:8000`) and `POST /sessions` → `POST /sessions/{handle}/edit`
→ `POST /sessions/{handle}/save`, mirroring the tracked tools. Schema at
[`integrations/openapi.json`](../integrations/openapi.json).

---

## See the changes

Whichever path you used, you get the same `.changex` journal and the same three
visualizations:

```bash
changex review report.changex --out review.html      # single-file HTML report / link
changex view   report.changex --doc report.docx      # local 127.0.0.1 webserver
# …or just open the tracked .docx in Word for native accept/reject revisions.
```

See also: [INTEGRATION.md](INTEGRATION.md) (capture modes + provenance) ·
[`packages/mcp/README.md`](../packages/mcp/README.md) (MCP tool contract) ·
[INSTALL.md](INSTALL.md) · [FIDELITY.md](FIDELITY.md) · [ARCHITECTURE.md](ARCHITECTURE.md).
