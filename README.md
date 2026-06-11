<p align="center">
  <img src="docs/assets/banner.svg" alt="ChangeX — see exactly what an AI changed, line by line, with receipts" width="820">
</p>

<h1 align="center">📝 ChangeX</h1>

<p align="center"><b>An AI just edited your document. Do you actually know what it changed?</b></p>

<p align="center">
  <a href="https://pypi.org/project/changex/"><img src="https://img.shields.io/pypi/v/changex.svg?logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/changex/"><img src="https://img.shields.io/pypi/pyversions/changex.svg" alt="Python"></a>
  <a href="https://github.com/ArioMoniri/changex/actions/workflows/ci.yml"><img src="https://github.com/ArioMoniri/changex/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

<p align="center">
Everyone hands documents to AI now — <i>"tighten the intro," "fix the citations," "redo the abstract."</i>
It gives the file back looking polished, and you have no real way to see <b>what it actually touched</b>.
Fine for a grocery list. Not fine for a manuscript, a contract, or anything with your name on it — where a
flipped number, a citation to a paper that doesn't exist, or a sentence the model quietly invented can ride
along unnoticed in a wall of text. Re-reading 30 pages to find it isn't a plan.
</p>

<p align="center">
ChangeX records <b>every edit the AI makes</b> —
<code>.docx</code> · <code>.xlsx</code> · <code>.csv</code> · <code>.pptx</code> · <code>.md</code> · <code>.doc</code> —
as real Word <b>tracked changes</b> you accept or reject one at a time, with a tamper-evident log of who did
what, when, and why. Less "diff between two files," more <b>flight recorder for your document</b>. 🛟
</p>

<p align="center">
  <a href="https://pypi.org/project/changex/"><img src="docs/assets/btn-install.svg" height="44" alt="uv tool install changex"></a>
  &nbsp;
  <a href="docs/CLAUDE-SETUP.md"><img src="docs/assets/btn-claude.svg" height="44" alt="Use from Claude & any model"></a>
  &nbsp;
  <a href="docs/"><img src="docs/assets/btn-docs.svg" height="44" alt="Read the docs"></a>
</p>

<p align="center">
  <img src="docs/assets/docx.png" alt="A multi-section report in ChangeX — the AI's edits inline in the document's own outline, with a who/why change-log" width="720">
  <br><sub><em>ChangeX's default view: every AI edit inline in the document's own outline, plus a who/why change-log.</em></sub>
</p>

---

## 🚀 Quickstart

```bash
# 1) install the tool
uv tool install changex                      # or: pipx install changex · pip install changex

# 2) connect it to every AI app you have — Claude Code, the Claude Desktop app, Cursor, Gemini
changex connect all                          # then ⌘Q + reopen the Claude Desktop app once
#    (the ChangeX Viewer app does this for you automatically on first launch)

# 3) ask your assistant, e.g.:
#    "Use changex to open report.docx, tighten the intro as tracked changes,
#     save it, then show me a review of what changed."
```

That's it — every edit lands as a **real Word tracked change** you can accept/reject, with full provenance. No MCP, a local/offline model, or a human editing by hand? → **[Without tools](#-how-it-works)** below.

<details>
<summary><b>🔄 Updating — what to update, and how</b></summary>

<br>

**There's only one thing to update: the `changex` package.** The MCP server (`changex-mcp`) and every CLI command ship *inside* it — you never update those separately.

**1. Update the package — use the same installer you installed with:**

| If you installed with… | …update with |
|---|---|
| `uv tool install changex` | `uv tool upgrade changex` |
| `pipx install changex` | `pipx upgrade changex` |
| `pip install changex` | `pip install -U changex` |
| `uvx changex` *(zero-install)* | nothing — `uvx` always runs the latest |

Confirm it worked: **`changex --version`**.

> **Still on the old version after upgrading?** PyPI's install index can lag a release by a few minutes, so `pip` may grab the previous version (and leave a sub-package like `changex-core` behind). Force a clean upgrade of all of them — `pip install -U --no-cache-dir changex changex-core changex-mcp changex-api` — or just `uv tool upgrade changex`, which handles it cleanly.

**2. The MCP server updates automatically.** Because `changex-mcp` is part of the package, step 1 upgrades it too. Your Claude registration is just a pointer to the `changex-mcp` binary, so **do *not* re-run `claude mcp add` to "update" it** — that doesn't update anything, it only creates duplicate entries. It picks up the new version next time it launches.

> Registered the MCP as `uvx changex-mcp` (zero-install) instead of the binary? That form is pinned to a cached version — get the newest with `uvx changex-mcp@latest`, or switch to the installed binary (below).

**Only touch `claude mcp` to (re)connect or fix duplicates.** Register **once** with `-s user` so it works in every folder and never duplicates. If you already added it in several folders without `-s user`, reset to a single clean entry:

```bash
claude mcp remove changex                    # repeat in each folder you added it to
claude mcp add -s user changex -- changex-mcp
claude mcp list                              # changex → ✓ Connected
```

</details>

---

## 🧭 How it works

<p align="center">
  <img src="docs/assets/flow.svg" alt="ChangeX flow: open → edit → seal → review" width="760">
</p>

There are **two ways** to capture an AI's edits — pick based on what your model can do:

| Path | Use it when | Provenance |
|------|-------------|------------|
| **🤖 From your AI (MCP)** | a tool-capable desktop client (Claude Desktop/Code, Cursor, Cline) | **full** — who / vendor / turn / prompt, per edit |
| **🪄 Without tools (`open`/`seal`)** | any model, offline/local, a script, or a human | **what-changed** (who/why is degraded — said out loud) |

Either way you get a portable, hash-chained **`.changex`** journal plus a tracked document to review.

<details>
<summary><b>🤖 Path A — from your AI (full provenance)</b></summary>

<br>

With the MCP server connected (Quickstart step 2), just ask in plain language. The model edits **through** ChangeX (`open_tracked → get_outline → read_node → edit → save_tracked`), so every change is a real Word revision — nothing silently rewritten. (`read_node` lets it pull a paragraph's full text before editing, so it never has to guess wording it can't see — a clinical or legal detail won't get broken by a blind edit.)

> *"Use changex to open `~/Documents/Q3-report.docx`. Tighten the executive summary, fix the heading levels, and replace the passive voice in section 2 — make every change a **tracked revision** authored by you, save it, then show me a review of what changed."*

⚠️ **Each Claude app is set up separately — this trips everyone up:**

- **Claude Code** (terminal / IDE) — `claude mcp add -s user changex -- changex-mcp` (Quickstart step 2). This is the *only* thing `claude mcp list ✓ Connected` reflects.
- **Claude Desktop app** — has its **own** config; `claude mcp add` does **not** touch it. Add changex there (absolute path) and **fully restart the app** → [docs/CLAUDE-SETUP.md §B](docs/CLAUDE-SETUP.md).
- **claude.ai / ChatGPT in a browser** — can't read local files *at all*; use a desktop app, or Path B on a downloaded copy.

So if `claude mcp list` says `✓ Connected` but a chat says *"I can't find changex / upload the file,"* you're talking to a **different Claude than the one you configured** — set it up for that app too, see **[🔌 Set up your app](#-set-up-your-app)** below. [Why local-only →](docs/LOCAL-ACCESS.md)

**📎 Easiest in Claude Desktop — just upload the doc.** Drag your `.docx` into the chat and say *"use changex to tighten the intro and fix the heading, then give me the tracked file."* The upload lands where the changex MCP can read it (no Full Disk Access needed — it sidesteps the macOS privacy wall entirely). changex saves the **tracked `.docx` + `.changex`** and Claude hands them back as downloads.

</details>

<details>
<summary><b>🪄 Path B — without tools, from any model or a human</b></summary>

<br>

No MCP, no tool-calling, no SDK. Three steps:

1. **`changex open report.docx`** — snapshot the original.
2. **Let anything edit `report.docx` in place** — Claude, ChatGPT, a local llama, a script, or you.
3. **`changex seal report.docx`** — ChangeX diffs against the snapshot and reconstructs the changes into `report.changex` + a Word-openable `report.tracked.docx`.

<p align="center">
  <img src="docs/assets/terminal.svg" alt="Terminal: changex open report.docx, edits happen, then changex seal report.docx" width="760">
</p>

This path sees only before-and-after bytes, so it records a **faithful *what-changed*** but **degraded *who/why*** (agent / turn / prompt are `null`) — and ChangeX says so. For full provenance, use Path A.

</details>

---

## 🔌 Set up your app

> **Installed the ChangeX Viewer app?** It **auto-connects every installed app on launch**
> (macOS & Windows) — Claude Code, the Claude Desktop app, Cursor, and the Gemini CLI. Just open
> it once, then ⌘Q + reopen Claude Desktop. No command needed. The button in **Viewer ▸ Settings ▸
> Use ChangeX in your AI apps** re-runs it any time.

**Or one command writes the config for you:**

```bash
changex connect all              # ⚡ connect EVERY installed local app at once
changex connect                  # list every app it can set up
changex connect claude-desktop   # writes the Desktop app config  (then ⌘Q + reopen)
changex connect cursor           # writes ~/.cursor/mcp.json
changex connect chatgpt          # prints the ChatGPT connector runbook (token + commands)
```

`changex connect <app>` merges the right MCP entry into that app's config — **backing the file up first** and using the absolute `changex-mcp` path so GUI apps find it. Targets: `claude-code` · `claude-desktop` · `cursor` · `cline` · `gemini` · `chatgpt` · `claude-web`.

Or wire it by hand — ChangeX plugs in three ways (**local MCP** = the app spawns `changex-mcp`; **remote MCP** = the app dials a URL; **REST/function tools**). Pick your app:

| Your app | How it connects | Reads local files? |
|---|---|---|
| **Claude Code** (terminal / IDE) | local MCP — one command | ✅ |
| **Claude Desktop app** | local MCP — *its own* config + restart | ✅ |
| **ChatGPT** (desktop or web) | remote MCP connector, or a custom-GPT Action | ✅ *(server runs on your Mac)* |
| **claude.ai** (web) | remote MCP connector | ✅ *(server runs on your Mac)* |
| **Cursor / Cline** | local MCP — config block | ✅ |
| **Gemini** (CLI / API) | local MCP / function tools | ✅ |
| **Ollama / LM Studio** | local MCP if supported, else the no-tools path | ✅ |

> 💡 GUI apps run with a minimal `PATH`, so in their config files use the **absolute** path from `which changex-mcp` (commonly `/opt/homebrew/bin/changex-mcp`). CLI clients launched from your shell usually find a bare `changex-mcp`.

<details>
<summary><b>🟧 Claude Code (terminal / IDE)</b></summary>

<br>

> **One command:** `changex connect claude-code` — or by hand:

```bash
claude mcp add -s user changex -- changex-mcp   # once; works in every folder, no duplicates
claude mcp list                                 # changex → ✓ Connected
```

This is the **only** thing `claude mcp list` reflects — it does *not* configure the Claude Desktop app (below).

</details>

<details>
<summary><b>🟧 Claude Desktop app</b> (separate from Claude Code!)</summary>

<br>

> **One command:** `changex connect claude-desktop`, then ⌘Q + reopen. Or by hand:

1. Get the absolute path: `which changex-mcp` → e.g. `/opt/homebrew/bin/changex-mcp`.
2. Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
   ```json
   { "mcpServers": { "changex": { "command": "/opt/homebrew/bin/changex-mcp", "args": [] } } }
   ```
3. **Fully quit & reopen** the app (⌘Q — not just close the window). The 🔨 tools icon should list `open_tracked`, `edit`, `save_tracked`, …

[Step-by-step → docs/CLAUDE-SETUP.md](docs/CLAUDE-SETUP.md)

</details>

<details>
<summary><b>🟩 ChatGPT (desktop or web)</b></summary>

<br>

> **One command:** `changex connect chatgpt` prints the token + exact commands below.

ChatGPT dials a **URL** (it can't reach `localhost`), so run the HTTP server and expose it with a tunnel — the server runs on your Mac, so it still edits your **local** files:

```bash
export CHANGEX_MCP_TOKEN=$(openssl rand -hex 32)
changex-mcp --http                                # serves http://127.0.0.1:9000/mcp
cloudflared tunnel --url http://127.0.0.1:9000    # or: ngrok http 9000  → an https URL
```

- **MCP connector** (Settings → Connectors, developer mode): add an MCP server → URL `https://<tunnel>/mcp`, header `Authorization: Bearer <CHANGEX_MCP_TOKEN>`.
- **Custom GPT → Actions:** instead run `changex-api` and import `https://<tunnel>/openapi.json` in the GPT's *Actions → Import from URL*.

[Full recipe → docs/CALL-FROM-YOUR-APP.md](docs/CALL-FROM-YOUR-APP.md)

</details>

<details>
<summary><b>🟦 claude.ai (web)</b></summary>

<br>

Same as the ChatGPT connector — run `changex-mcp --http` + a tunnel + a token, then **Settings → Connectors → Add custom connector**: URL `https://<tunnel>/mcp`, auth header `Authorization: Bearer <CHANGEX_MCP_TOKEN>`. (A web tab can't read local files itself; the tunneled server does the file I/O on your Mac.)

</details>

<details>
<summary><b>🟪 Cursor / Cline</b></summary>

<br>

> **One command:** `changex connect cursor` (or `changex connect cline`). Or by hand:

Add to `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global) — Cline uses the same block in its MCP settings:

```json
{ "mcpServers": { "changex": { "command": "changex-mcp", "args": [] } } }
```

</details>

<details>
<summary><b>🟨 Gemini (CLI / API)</b></summary>

<br>

> **One command (CLI):** `changex connect gemini`. Or by hand:

**CLI** — add to `~/.gemini/settings.json`:

```json
{ "mcpServers": { "changex": { "command": "changex-mcp", "args": [] } } }
```

**API** — load [`integrations/gemini-functions.json`](integrations/gemini-functions.json) (function declarations) and route each call to the matching `changex-api` endpoint.

</details>

<details>
<summary><b>⬛ Ollama / LM Studio (local models)</b></summary>

<br>

- **Speaks MCP?** (LM Studio, recent builds) — register the same stdio block:
  ```json
  { "mcpServers": { "changex": { "command": "changex-mcp", "args": [] } } }
  ```
- **Doesn't?** (plain Ollama) — use the **no-tools path**: `changex open report.docx` → let the model rewrite the file → `changex seal report.docx`. Same as [Path B](#-how-it-works) above.

</details>

> Flags, security (loopback vs `--public` + token), the OpenAI Agents SDK, and REST/function-tool schemas: **[docs/CALL-FROM-YOUR-APP.md](docs/CALL-FROM-YOUR-APP.md)**.

---

## 👀 Review the changes

`changex seal` prints these with your real paths — or run them yourself:

```bash
changex review report.changex --out review.html                            # 🐙 GitKraken-style commit graph
changex log    report.changex                                              # 🌿 git-log of every edit (--oneline)
changex rewind report.changex original.docx --to 3 --out phase3.docx        # ⏪ the doc at any earlier phase
changex verify report.changex                                              # 🔒 hash-chain tamper check
changex view   report.changex --doc report.tracked.docx                     # 🌐 live local page (accept/reject)
changex preview report.changex --out preview.html                           # 🔎 self-contained HTML (any platform)
#  …or just open report.tracked.docx in Word — real native track changes 🖊️
```

Because the `.changex` journal is an **append-only, hash-chained** log of edits — each op is a
"commit" (`hash` ⭢ `prev_hash`) stamped with **author + timestamp** — ChangeX gives you a git-like
history of any document:

- **🐙 `changex review` → a GitKraken-style commit graph.** Every document **part** (paragraph)
  is its own coloured **lane** — a continuous *follow line* you can trace down the graph through
  every edit that touched it. Each commit shows its hash, op kind, the part, the redline (red
  delete / green insert), the author avatar, the timestamp, and the rationale. The **same graph
  shows in the ChangeX Viewer** app and `changex view`.
- **⏪ `changex rewind` → time-travel.** Rebuild the document as it was at *any* earlier phase:
  `--to <seq|hash>` replays the baseline + the first N edits (`--to 0` = the clean baseline).
- **🌿 `changex log` → the terminal view** (`--oneline` too).

<p align="center">
  <img src="docs/assets/commit-graph.png" width="760"
       alt="ChangeX commit graph — every edit is a commit on a coloured graph rail; each document part is its own lane (a follow line) you can trace through its edits, with hash, op kind, the part, the redline, author avatar, timestamp, and rationale">
</p>

```text
$ changex log "Q3 Launch Brief.changex" --oneline
d27c085  text.replace  by the end of the quarter → by September 30          (Claude, 2026-06-08 09:12)
3edcc9f  text.insert   + across three regions                              (GPT-4o, 2026-06-08 09:31)
671985a  text.replace  all of our customers worldwide → enterprise …       (Claude, 2026-06-08 10:02)
3a93438  text.replace  approximately fifty thousand dollars → $48,000      (Sam,    2026-06-08 11:20)
852ec26  text.replace  reduce risk → minimize downtime                     (GPT-4o, 2026-06-08 13:46)
f39f63e  style.change  Normal → Title                                      (Gemini, 2026-06-08 14:05)
99be3fa  text.replace  redesigned dashboard → redesigned analytics …       (Claude, 2026-06-08 16:41)

$ changex rewind "Q3 Launch Brief.changex" original.docx --to 3 --out phase3.docx
✓ rewound to seq 3 (671985a54) — 3 of 7 edits applied
```

`changex preview` renders **any** file to a self-contained HTML page — a `.changex` journal
as a redline, or a **source-code/text file with syntax highlighting** (Pygments). It's the
engine behind the macOS Quick Look extension and the Windows preview handler below, so a
double-click preview looks the same everywhere.

💡 Paths with spaces need quotes: `changex open "My Report.docx"`.

---

## 📦 What it tracks

| Format | How changes show up |
|--------|---------------------|
| 📄 `.docx` | **Native Word track changes** — accept/reject in Word (text, paragraph, style, run-format, paragraph move) |
| 📊 `.xlsx` / `.csv` | Non-destructive review copy — colored cells, comments, a `Changes` sheet (original untouched) |
| 📽️ `.pptx` | Revision overlay + a generated "Revisions" summary slide |
| 📝 `.md` | Inline HTML redline (Markdown has no native track-changes) |
| 🗂️ `.doc` (legacy) | Auto-converted to `.docx` (LibreOffice), then native Word revisions — best-effort |

Every format also writes the portable **`.changex`** journal. Honest per-format limits: [docs/FIDELITY.md](docs/FIDELITY.md). Live **MCP** and the **`open`/`seal`** path are docx-only; other formats are captured with scripted **`changex track`** (see **Example prompts** below).

<details>
<summary>🖼️ <b>See it on every format</b></summary>

<br>

| Markdown — inline redline | CSV — side-by-side redline |
|:--:|:--:|
| <img src="docs/assets/md.png" width="380"> | <img src="docs/assets/csv.png" width="380"> |
| **Excel** — review + provenance | **PowerPoint** — review |
| <img src="docs/assets/xlsx.png" width="380"> | <img src="docs/assets/pptx.png" width="380"> |

</details>

---

## 📖 More

<details>
<summary><b>✍️ Example prompts (copy-paste)</b></summary>

<br>

Talk to ChangeX in plain language through your AI — each prompt notes what it does:

> **Tighten + restyle** — *"Open `report.docx` with changex. Replace every "utilize" with "use", fix the two run-on sentences in the intro, and bold the section headings — all as tracked revisions. Save and show me the review."*

> **Proofread, one change each** — *"Using changex, proofread `notes.docx` for grammar only. Make each fix a separate tracked change with a one-line rationale, then give me the change-log grouped by paragraph."*

> **Move a section** *(exercises `node.move`)* — *"Open `contract.docx`, move the "Termination" clause to just after "Payment" as a tracked move, and don't touch anything else."*

**Scripted edits (any format, no model)** — hand `changex track` a small `ops.json` for that one file, e.g. a spreadsheet:

```json
[
  { "kind": "cell.set", "sheet": "Q4", "ref": "B3", "before": "95", "after": "120", "rationale": "cloud spend rose" },
  { "kind": "formula.set", "sheet": "Q4", "ref": "C3", "before": "=B3*1.1", "after": "=B3*1.15", "rationale": "higher growth" }
]
```

```bash
changex track budget.xlsx ops.json --out budget.tracked.xlsx --changex budget.changex
changex view  budget.changex --doc budget.tracked.xlsx
```

(For `.docx`, ops are `text.replace` / `node.insert` / `style.change` / `format.run` / `node.move` by `node_id` — see [docs/CHANGEX_FORMAT.md](docs/CHANGEX_FORMAT.md).)

</details>

<details>
<summary><b>🖥️ CLI commands</b></summary>

<br>

Run `changex` (or `changex help`) for the full list:

```text
 ╔═╗╦ ╦╔═╗╔╗╔╔═╗╔═╗═╗ ╦
 ║  ╠═╣╠═╣║║║║ ╦║╣ ╔╩╦╝
 ╚═╝╩ ╩╩ ╩╝╚╝╚═╝╚═╝╩ ╚═
 provenance-first change tracking for AI document edits

  Track & review
    track    apply ops to a doc (.docx/.xlsx/.csv/.pptx/.md/.doc) → tracked file + .changex
    review   render the changes as a GitKraken-style commit graph (HTML)
    log      git-log of every edit (--oneline)
    rewind   reconstruct the document at any earlier phase (git checkout)
    preview  render ANY file to self-contained HTML (redline, or highlighted code/text)
    view     serve an interactive localhost review page (accept / reject)
    verify   check a .changex hash chain + baseline

  Passive — any model, even offline
    open     snapshot the baseline before anything edits the file
    seal     diff the edited file → reconstruct the tracked changes

  Connect to your apps
    connect  wire ChangeX into your AI apps  (`connect all` = every installed one at once)

  Diagnose & set up (macOS)
    doctor     diagnose install + file-access (Full Disk Access)
    quicklook  manage the Finder Quick Look preview for .changex & code files

  Extras
    shell    interactive Python shell with changex_core preloaded
    help     show this command list
```

`changex shell` opens a Python REPL with `changex_core` preloaded; `changex --version` prints the version.

</details>

<details>
<summary><b>💻 Desktop app (optional) + downloads</b></summary>

<br>

ChangeX ships an optional **[Tauri](https://tauri.app)** desktop viewer — a small, double-clickable window over the **same** review UI as `changex view`.

It opens on two views you flip between:

- **Commit graph** — a GitKraken-style timeline where every edit is a commit and each paragraph rides its own coloured lane, so you can trace one part through all its edits.
- **Document** — your tracked `.docx` shown *as the document itself*: the real text, in order, with the AI's insertions and deletions marked inline (hover a change for who/when). Drop a `.changex` next to its tracked `.docx` and the app finds the doc and opens this view on its own.

**You usually don't need the app.** `changex view` (zero-install local page) and the single-file HTML report already give the full accept/reject review on every platform. The desktop window mostly buys you a native icon to double-click for non-technical reviewers — plus that read-the-document-in-context view above.

<p align="center">
  <a href="https://github.com/ArioMoniri/changex/releases/latest/download/ChangeX-Viewer-macos.dmg"><img src="docs/assets/btn-mac.svg" height="44" alt="Download macOS .dmg"></a>
  &nbsp;
  <a href="https://github.com/ArioMoniri/changex/releases/latest/download/ChangeX-Viewer-windows.msi"><img src="docs/assets/btn-win.svg" height="44" alt="Download Windows .msi"></a>
  &nbsp;
  <a href="https://github.com/ArioMoniri/changex/releases/latest/download/ChangeX-Viewer-linux.AppImage"><img src="docs/assets/btn-linux.svg" height="44" alt="Download Linux .AppImage"></a>
</p>

Installers attach to **[tagged releases](https://github.com/ArioMoniri/changex/releases)**: macOS `.dmg` is **signed + notarized**; Windows `.msi` and Linux `.AppImage`/`.deb` are unsigned. Build/sign details: [docs/CI-AND-SECRETS.md](docs/CI-AND-SECRETS.md).

</details>

<details>
<summary>🔎 <strong>Finder / Explorer preview — press Space to see the redline</strong></summary>

Preview a `.changex` journal (or any source file, syntax-highlighted) right from your file
manager — no app to open.

- **macOS — Quick Look.** Grab `ChangeX-QuickLook.dmg` from the [latest release](https://github.com/ArioMoniri/changex/releases/latest) (signed + notarized), or just open **ChangeX Viewer ▸ Settings ▸ Enable** and it installs + turns on the preview for you. Then select a `.changex` (or `.py`, `.ts`, `.json`, …) in Finder and press **Space**. The helper is a background agent — **no Dock icon**. Manage it any time with `changex quicklook status|enable|disable`.
- **Windows — Explorer preview pane.** Grab `ChangeX-Windows-Preview.zip` from the latest release and run `install.ps1` (it registers a preview handler that shells out to `changex preview`). Select a file and open the preview pane (**Alt+P**). Requires `pip install "changex[preview]"`.

Both reuse the same `changex preview` engine, so the preview looks identical across platforms.

</details>

---

## 🛟 Troubleshooting

<details open>
<summary><b>"can't open my file" / <code>Operation not permitted</code> (macOS) — even via Claude</b></summary>

<br>

This is **macOS privacy (TCC)**, not a changex bug: macOS blocks the *controlling app* (Claude
Desktop, Terminal, iTerm, VS Code…) from `~/Downloads`, `~/Documents`, and `~/Desktop`. The
`changex-mcp` server inherits that app's permission, so it's blocked exactly when the app is.

Run **`changex doctor`** — it names the exact app to grant, shows which folders are blocked, and links you straight to the settings pane:

```bash
changex doctor                  # diagnose
changex doctor --open-settings  # also open Full Disk Access
```

**Fix (one-time):** quit the app (⌘Q) → **System Settings → Privacy & Security → Full Disk Access** → turn **ON** that app (e.g. **Claude**) → reopen it. In the **ChangeX Viewer** app, the **Grant access** button opens this pane for you.

**Or skip permissions entirely:** in **Claude Desktop, upload the document into the chat** and ask changex to edit it — the upload lands where changex can read it. Or move the file out of those protected folders.

</details>

<details>
<summary><b>MCP server shows <code>✗ Failed to connect</code> (with <code>uvx</code> / <code>npx</code>)</b></summary>

<br>

The first `uvx changex-mcp` / `npx -y …` downloads the package + all deps into a fresh environment, which can exceed the MCP health-check timeout — so `claude mcp list` says *Failed to connect* even though the server is fine. **Fix — register the installed binary at user scope:**

```bash
claude mcp remove changex                 # drop any old uvx / per-folder entry
claude mcp add -s user changex -- changex-mcp
claude mcp list                           # changex should now show ✓ Connected
```

Prefer the zero-install `uvx` form? Warm the cache first: `uv tool install changex-mcp`.

</details>

<details>
<summary><b><code>WARNING: Cache entry deserialization failed, entry ignored</code> on <code>pip install</code></b></summary>

<br>

This is a **pip HTTP-cache warning, not a changex failure** — pip skipped a stale cache entry; the install still succeeds. To clear it:

```bash
python3 -m pip cache purge
python3 -m pip install -U changex --break-system-packages --no-cache-dir
```

If `pip` still reports an older version afterwards, the new one may not be on PyPI yet (the index CDN can lag a few minutes) — wait, or install from source (`git clone … && uv sync`).

</details>

<details>
<summary><b><code>error: externally-managed-environment</code> (PEP 668)</b></summary>

<br>

Your system Python refuses a global `pip install`. Use an isolated installer: `uv tool install changex` (or `pipx install changex`). If you must use `pip`, add `--break-system-packages`.

</details>

<details>
<summary><b>Legacy <code>.doc</code> won't open · paths with spaces</b></summary>

<br>

- **`.doc`** is converted to `.docx` via **LibreOffice** — install it and ensure `soffice` is on `PATH` (best-effort, lossy for exotic legacy features).
- **Paths with spaces** must be quoted: `changex open "My Report.docx"`.
- **Browser chats** can't read local files — use a desktop client, or `open`/`seal` on a downloaded copy.

</details>

---

## ℹ️ About

**ChangeX is a provenance-first change tracker for AI document edits.** It records *what* changed, *in what order*, and *who/why* — as a portable, hash-chained **`.changex`** journal — and projects that onto whatever review surface the format supports: **native Word track-changes** for `.docx`, a non-native overlay for `.xlsx` / `.csv` / `.pptx` / `.md`. It's **local-first** (no network calls in the core) and **vendor-neutral** (MCP + CLI behave the same across Claude, ChatGPT, Gemini, and local models). Design principle: **honesty over hype** — a degraded/reconstructed result is never presented as full provenance.

> **Repository description** *(GitHub "About" field):* Provenance-first change tracking for AI document edits — native Word track-changes + a portable, hash-chained `.changex` journal. Works with any model (MCP + CLI). docx · xlsx · csv · pptx · md.

<details>
<summary><b>📦 Published packages</b></summary>

<br>

All on PyPI (MIT) — `pip install changex` pulls them all:

| Package | What it is |
|---|---|
| [![changex](https://img.shields.io/pypi/v/changex?label=changex&color=3775A9&logo=pypi&logoColor=white)](https://pypi.org/project/changex/) | umbrella — installs the CLI **and** the MCP server |
| [![changex-core](https://img.shields.io/pypi/v/changex-core?label=changex-core&color=3775A9&logo=pypi&logoColor=white)](https://pypi.org/project/changex-core/) | the engine — model, journal, adapters, renderers, CLI |
| [![changex-mcp](https://img.shields.io/pypi/v/changex-mcp?label=changex-mcp&color=3775A9&logo=pypi&logoColor=white)](https://pypi.org/project/changex-mcp/) | the MCP server (stdio + remote HTTP) |
| [![changex-api](https://img.shields.io/pypi/v/changex-api?label=changex-api&color=3775A9&logo=pypi&logoColor=white)](https://pypi.org/project/changex-api/) | FastAPI REST + OpenAPI wrapper |

</details>

---

🤝 **Contributing:** see [CONTRIBUTING.md](CONTRIBUTING.md) · follow the [Code of Conduct](CODE_OF_CONDUCT.md)
&nbsp;·&nbsp; 🗺️ **Docs:** [Install](docs/INSTALL.md) · [Architecture](docs/ARCHITECTURE.md) · [.changex format](docs/CHANGEX_FORMAT.md) · [Fidelity](docs/FIDELITY.md) · [CI & secrets](docs/CI-AND-SECRETS.md)
&nbsp;·&nbsp; 📜 **License:** [MIT](LICENSE) — © 2026 Ariorad Moniri
