# Installing ChangeX

> Status: **how-to.** Everything you need to get the `changex` CLI and the
> `changex-mcp` server onto your machine, wire the server into any AI client, and
> verify it works. For the cross-vendor MCP matrix and provenance details see
> [INTEGRATION.md](INTEGRATION.md); for the honest per-format limits see
> [FIDELITY.md](FIDELITY.md).

ChangeX ships as **one installable name** — `changex` — a meta package that pulls in
the two real packages and puts **two commands** on your PATH:

| Command | What it is | From package |
|---------|-----------|--------------|
| `changex` | the CLI: `track` / `review` / `verify` / `view` / `open` / `seal` | `changex-core` |
| `changex-mcp` | the MCP **stdio** server an AI client connects to | `changex-mcp` |

Requires **Python ≥ 3.11**.

---

## 1. Quick install (recommended)

Pick whichever package manager you already use. All three install the single
`changex` name and expose both commands.

```bash
# uv — isolated tool install, fastest (https://docs.astral.sh/uv/)
uv tool install changex

# pipx — isolated per-tool environments
pipx install changex

# pip — into the active environment / venv
pip install changex
```

Verify:

```bash
changex --help          # CLI subcommands
changex-mcp --help 2>/dev/null || echo "changex-mcp is a stdio server (no --help; an MCP client drives it)"
```

### Zero-install (run once, nothing left behind)

`uvx` fetches and runs in an ephemeral environment — ideal for trying it or for an
MCP config that should always use the latest:

```bash
uvx changex --help        # the CLI, one-off
uvx changex-mcp           # the MCP server, one-off (this is what MCP configs invoke)
```

---

## 2. From source (this repo)

The repo is a **uv workspace**: the root `pyproject.toml` declares the workspace plus
the `changex` meta package, and each of `packages/core` / `packages/mcp` is a member.
A single sync wires everything together against one lockfile.

```bash
git clone https://github.com/ArioMoniri/changex
cd changex

# With uv (recommended): installs CLI + MCP server into ./.venv
uv sync                    # add --extra dev for pytest/ruff/mypy

# Without uv: editable-install both packages into your own venv
python -m venv .venv && source .venv/bin/activate
pip install -e packages/core -e packages/mcp
# dev extras:  pip install -e "packages/core[dev]" -e "packages/mcp[dev]"
```

A `Makefile` wraps the common flows:

```bash
make install     # uv sync         (CLI + MCP into .venv)
make dev         # uv sync --extra dev
make test        # pytest
make demo        # end-to-end demo on examples/sample.docx (see §5)
make mcp         # launch the MCP stdio server
make help        # list all targets
```

---

## 3. Wire the MCP server into your AI client

MCP **active-capture** is the strongest path: the model edits *through* ChangeX, so
provenance is captured at the source. Every client launches the same **stdio** server
(`uvx changex-mcp`; with a pip install, use `python -m changex_mcp`).

**Claude Code — one line:**

```bash
claude mcp add changex -- uvx changex-mcp
```

**Everyone else — the same stdio block** in the client's MCP config:

```json
{ "mcpServers": { "changex": { "command": "uvx", "args": ["changex-mcp"] } } }
```

| Client | Config location |
|--------|-----------------|
| Claude Code | `~/.claude.json` or project `.mcp.json` |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) · `%APPDATA%\Claude\claude_desktop_config.json` (Windows) |
| Gemini CLI | `~/.gemini/settings.json` |
| Cursor | `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global) |
| Cline / Continue | `cline_mcp_settings.json` · `~/.continue/config.json` |
| OpenAI Agents SDK | `MCPServerStdio(params={"command": "uvx", "args": ["changex-mcp"]})` |

Full per-vendor snippets and the "declare your model id" step are in
[INTEGRATION.md](INTEGRATION.md) §3.

> **No MCP client?** Use the passive path — it needs no tool-calling at all. See §5
> below and [INTEGRATION.md](INTEGRATION.md) §4.

---

## 4. Optional system dependency: LibreOffice (legacy `.doc` only)

`.docx` / `.xlsx` / `.csv` / `.pptx` are **pure-Python** — no system packages needed.

Only **legacy `.doc`** ingest needs **LibreOffice** (headless) on PATH for the
`.doc` → `.docx` conversion. This is **planned / experimental** (see
[FIDELITY.md](FIDELITY.md) §1) and is best-effort.

```bash
# macOS
brew install --cask libreoffice
# Debian / Ubuntu
sudo apt-get install libreoffice
# Fedora
sudo dnf install libreoffice
```

---

## 5. Verify the install (60-second demo)

From a source checkout, run the bundled end-to-end demo:

```bash
make demo            # or: ./scripts/demo.sh
```

It tracks two edits on `examples/sample.docx`, renders a single-file HTML report, and
verifies the hash chain — printing exactly where the tracked `.docx`, the `.changex`
journal, and the report landed (in `examples/out/`).

Or drive the CLI directly on any document:

```bash
# passive path — works with any model or a human editor
changex open  report.docx --changex report.changex
# … edit report.docx in place …
changex seal  report.docx --changex report.changex
changex verify report.changex --baseline report.docx
changex review report.changex --out review.html     # single-file report
changex view   report.changex --doc report.docx     # interactive local webserver
```

---

## 6. Troubleshooting

- **`changex: command not found`** — the install dir isn't on PATH. With uv, run
  `uv tool update-shell` (or restart your shell); with pipx, `pipx ensurepath`. From a
  source checkout, call `./.venv/bin/changex` or activate the venv.
- **`uvx changex-mcp` is slow on first run** — `uvx` builds an ephemeral environment
  the first time; it's cached afterward. For a persistent install use
  `uv tool install changex`.
- **MCP client doesn't see the server** — confirm `uvx changex-mcp` runs in a plain
  terminal (it should start and wait on stdio), then re-check the JSON block's
  `command`/`args`. A pip-only environment should use
  `{ "command": "python", "args": ["-m", "changex_mcp"] }`.
- **Python too old** — ChangeX needs **3.11+**. `uv tool install --python 3.12 changex`
  pins a newer interpreter.

See also: [INTEGRATION.md](INTEGRATION.md) · [FIDELITY.md](FIDELITY.md) ·
[ROADMAP.md](ROADMAP.md) · [`packages/mcp/README.md`](../packages/mcp/README.md).
