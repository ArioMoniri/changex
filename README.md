# ChangeX

**Provenance-first change tracking for AI document edits.**

ChangeX records *exactly* what an LLM (Claude, Gemini, OpenAI, or any MCP-capable
agent) changed in an Office document — `.docx`, `.xlsx`, `.csv`, `.pptx`, `.doc` —
**end to end, as the edits happen**, not by diffing two files after the fact.

Every change is captured as a structured, attributable operation: *what* changed,
*where*, *which model/agent/prompt* produced it, and *when*. ChangeX then renders
that history several ways:

1. **Native track changes inside the file** — real Word revisions (`<w:ins>`/`<w:del>`)
   for `.docx`. Excel and PowerPoint have **no native track-changes**, so there ChangeX
   renders a **non-native overlay** (colored cells + comments + a "Changes" audit sheet
   for `.xlsx`/`.csv`; revision callouts + a "Revisions" summary for `.pptx`) — see
   [docs/FIDELITY.md](docs/FIDELITY.md).
2. **A portable sidecar journal** (`.changex`) — an event-sourced, hash-chained log
   of every operation with provenance, independent of the document format.
3. **Lightweight visualization, your choice** —
   - a **single-file HTML report** (`changex review --out review.html`): no server,
     no deps, open locally or share as a link;
   - a **local review webserver** (`changex view`): an interactive `127.0.0.1` page
     with inline + side-by-side redline, a provenance timeline filterable by
     model/seq, and live accept/reject — nothing leaves the machine;
   - the document's **own native track changes** in Word;
   - an **optional desktop app** (Tauri, `packages/viewer`) over the same renderer.

## Install

> Full matrix (uv / pipx / pip, from-source, every MCP client, system deps) lives in
> **[docs/INSTALL.md](docs/INSTALL.md)**. The copy-paste essentials:

**Quick install** — one name gives you both the `changex` CLI and the `changex-mcp` server:

```bash
uv tool install changex      # recommended (isolated, fast)
# or
pipx install changex         # isolated via pipx
# or
pip install changex          # into the current environment
```

Zero-install, run once:

```bash
uvx changex --help           # the CLI
uvx changex-mcp              # the MCP stdio server
```

**From source** (this repo) — a uv workspace; one sync wires up both packages:

```bash
git clone https://github.com/ArioMoniri/changex && cd changex
uv sync                       # installs the CLI + MCP server into .venv
# …or without uv:
pip install -e packages/core -e packages/mcp
```

**Wire it into your AI client** (MCP active-capture, captures provenance at the source).
One line for Claude Code:

```bash
claude mcp add changex -- uvx changex-mcp
```

For every other client, drop this stdio block into the client's MCP config
(`~/.gemini/settings.json`, `.cursor/mcp.json`, Cline/Continue, Claude Desktop, OpenAI
Agents SDK — full list in [docs/INTEGRATION.md](docs/INTEGRATION.md)):

```json
{ "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
```

**Optional system dependency:** legacy `.doc` ingest needs **LibreOffice** (headless)
on PATH for the `.doc` → `.docx` conversion. Nothing else requires it; `.docx` / `.xlsx`
/ `.csv` / `.pptx` are pure-Python. Install via `brew install --cask libreoffice` (macOS)
or `apt-get install libreoffice` (Debian/Ubuntu).

## Quickstart (60 seconds)

ChangeX has **two interchangeable paths** that produce the **same** `.changex` journal
and the **same** visualizations. Pick whichever fits how your model runs.

### Path A — active capture (MCP): the model edits *through* ChangeX

1. Register the server (once): `claude mcp add changex -- uvx changex-mcp`.
2. In your MCP client, tell the agent to open and edit a doc. It calls
   `open_tracked` → `edit` → `save_tracked` and writes a tracked `.docx` plus a
   `.changex` journal — provenance captured live. Declare your model so revisions are
   authored correctly:

   ```jsonc
   open_tracked({ "path": "/abs/report.docx",
                  "agent_context": { "model": "claude-opus-4-8", "vendor": "anthropic" } })
   ```

   (Full tool contract: [`packages/mcp/README.md`](packages/mcp/README.md).)

### Path B — passive capture (no tools needed): `open` → edit → `seal`

Works with **any** model or human — Ollama, LM Studio, llama.cpp, a text box. Provenance
is honestly **degraded** here (who/why unknown; see [docs/FIDELITY.md](docs/FIDELITY.md)).

```bash
changex open  report.docx --changex report.changex   # snapshot the baseline
# … anything edits report.docx in place (model, script, or you) …
changex seal  report.docx --changex report.changex   # reconstruct the journal by diff
```

### See the changes — three visualizations, same journal

```bash
# 1. single-file HTML report (no server, no deps) — open locally or share as a link
changex review report.changex --out review.html
#    ...add --doc to show the changes INLINE in the document's own outline:
changex review report.changex --doc report-tracked.docx --out review.html

# 2. interactive local webserver (127.0.0.1; nothing leaves the machine)
changex view   report.changex --doc report.docx

# 3. the document's OWN native track changes — just open the tracked .docx in Word
```

> **Try it now, no setup beyond `uv sync`:** run `make demo` (or `./scripts/demo.sh`).
> It tracks two edits on `examples/sample.docx`, then `review`s and `verify`s them,
> printing exactly where the tracked `.docx`, the `.changex` journal, and the HTML
> report landed.

**Honesty note:** native in-file accept/reject is `.docx`-only; `.xlsx`/`.csv`/`.pptx`
ship a **journal + non-native overlay** (annotations / audit sheet / summary), since
those formats have no native track-changes concept. Passive capture is faithful for
*what changed* but **degraded** for *who/why*. Details in
[docs/FIDELITY.md](docs/FIDELITY.md).

## Why not just diff the files?

A diff answers "how do these two files differ." ChangeX answers
**"what did the AI actually do, in order, and why."** In active capture it records the
operation stream live (insert paragraph, set cell `B7=...`, delete slide 3, restyle
run), attributes each op to a model/turn/prompt, and can replay or selectively roll
back. When an edit happens outside the tracked tools, the `open`/`seal` fallback
reconstructs the operations by diff — faithfully recovering *what* changed, though in
that mode the *who/why* is unknown (honest, degraded provenance — see
[docs/FIDELITY.md](docs/FIDELITY.md)).

## How it integrates with the models — native to any model

ChangeX is native to *any* model through **two interchangeable paths** that produce
the **same** `.changex` journal and the **same** visualizations:

- **MCP active-capture** — the **MCP server** is the vendor-neutral seam across
  Claude, Gemini, OpenAI, Cursor, Cline, and any MCP client. The agent opens, edits,
  and saves *through* ChangeX tools, so provenance is captured at the source.
- **`changex open` / `seal` passive-capture** — for ANY model, including local/offline
  ones that can't call tools (Ollama, LM Studio, llama.cpp) and human-in-the-loop:
  `changex open` snapshots a baseline, anything edits the file in place, and
  `changex seal` reconstructs the attributed journal by diff. No SDK, no tool-calling.
  Provenance is honestly **degraded** in this mode (who/why unknown) — see
  [docs/FIDELITY.md](docs/FIDELITY.md).

A Claude **Skill** and a thin **CLI** wrap the same core. Copy-paste config for every
surface is in [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Call it from your app

Per-app, copy-paste recipes — real flags, URLs, and endpoints — live in
**[docs/CALL-FROM-YOUR-APP.md](docs/CALL-FROM-YOUR-APP.md)** (Claude Desktop/Code,
claude.ai connectors, ChatGPT connectors + custom-GPT Actions, OpenAI Agents/Responses,
Gemini CLI/API, Cursor, Cline, Ollama, LM Studio). The single most likely path for each
first-class target:

- **Claude** (Desktop / Code) — MCP over stdio:

  ```bash
  claude mcp add changex -- uvx changex-mcp
  ```

  (claude.ai web uses a *custom connector*: run `changex-mcp --http` → paste
  `http://127.0.0.1:9000/mcp` + a bearer token — see the recipe and its security note.)

- **ChatGPT / OpenAI** — a custom GPT **Action** pointed at the REST OpenAPI schema:

  ```bash
  uv sync && changex-api      # serves http://127.0.0.1:8000/openapi.json (the Action schema)
  ```

  (OpenAI Agents SDK can instead use the MCP stdio server directly.)

- **Gemini** — MCP over stdio (CLI), via `~/.gemini/settings.json`:

  ```json
  { "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
  ```

  (The Gemini API path uses the function declarations in
  [`integrations/gemini-functions.json`](integrations/gemini-functions.json).)

Honest caveats carry through: a **public** MCP/REST bind is refused without a bearer
token (loopback is the safe default), and the **passive** `open`/`seal` fallback for
no-tool-calling models is faithful for *what* changed but **degraded** for *who/why* (see
[docs/FIDELITY.md](docs/FIDELITY.md)).

## Status

🚧 Early build, but the core is end-to-end. **Available today:**

- **`.docx`** — the full spine: MCP active-capture, `changex open`/`seal`
  passive-capture, the `.changex` journal, the single-file HTML report
  (`changex review`), and the local review webserver (`changex view`), with **native
  Word revisions** for in-file accept/reject.
- **`.xlsx` / `.csv` / `.pptx`** — **Available** as **journal + non-native overlay**
  (colored cells + comments + a "Changes" audit sheet for spreadsheets; revision
  callouts + a "Revisions" summary for slides). These formats have **no native
  track-changes**, so review lives in the journal + overlay, **not** host-app
  accept/reject. Same `.changex` journal and same `review`/`view` surfaces as docx.

**Still planned:** legacy `.doc` ingest (via LibreOffice conversion) and the optional
Tauri desktop app. See [docs/ROADMAP.md](docs/ROADMAP.md) for milestones,
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design, and
[docs/FIDELITY.md](docs/FIDELITY.md) for the honest per-format and per-capture-mode limits.

## Repo layout

```
packages/core     changex-core   — canonical model, adapters, journal, renderers, diff (Python)
packages/mcp      changex-mcp    — MCP server exposing tracked open/edit/save tools (Python)
packages/viewer   changex-viewer — Tauri + React desktop review app
skill/            Claude Skill packaging of the core
docs/             roadmap, architecture, .changex format spec, integration guide, fidelity/limits
examples/         sample documents and tracked sessions
```

## License

MIT (intended).
