<p align="center">
  <img src="docs/assets/banner.svg" alt="ChangeX — see exactly what an AI changed, line by line, with receipts" width="820">
</p>

<h1 align="center">📝 ChangeX</h1>

<p align="center"><b>See <i>exactly</i> what an AI changed in your documents — line by line, with receipts.</b></p>

<p align="center">
  <a href="https://pypi.org/project/changex/"><img src="https://img.shields.io/pypi/v/changex.svg?logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/changex/"><img src="https://img.shields.io/pypi/pyversions/changex.svg" alt="Python"></a>
  <a href="https://github.com/ArioMoniri/changex/actions/workflows/ci.yml"><img src="https://github.com/ArioMoniri/changex/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

<p align="center">
ChangeX captures <b>every edit an AI makes</b> to your documents —
<code>.docx</code> · <code>.xlsx</code> · <code>.csv</code> · <code>.pptx</code> · <code>.md</code> · <code>.doc</code> —
<i>as it happens</i>, with <b>who / what / when / why</b>.<br>
A diff tells you <i>how two files differ</i>; ChangeX tells you <b>what the AI actually did, in order, and why</b> — and lets you accept or reject each change. 🎯
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

# 2) connect it to Claude CODE (terminal / IDE) — once; works in every folder, no duplicates
#    chatting in the Claude DESKTOP app instead? that's a SEPARATE config → docs/CLAUDE-SETUP.md
claude mcp add -s user changex -- changex-mcp

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

With the MCP server connected (Quickstart step 2), just ask in plain language. The model edits **through** ChangeX (`open_tracked → get_outline → edit → save_tracked`), so every change is a real Word revision — nothing silently rewritten.

> *"Use changex to open `~/Documents/Q3-report.docx`. Tighten the executive summary, fix the heading levels, and replace the passive voice in section 2 — make every change a **tracked revision** authored by you, save it, then show me a review of what changed."*

⚠️ **Each Claude app is set up separately — this trips everyone up:**

- **Claude Code** (terminal / IDE) — `claude mcp add -s user changex -- changex-mcp` (Quickstart step 2). This is the *only* thing `claude mcp list ✓ Connected` reflects.
- **Claude Desktop app** — has its **own** config; `claude mcp add` does **not** touch it. Add changex there (absolute path) and **fully restart the app** → [docs/CLAUDE-SETUP.md §B](docs/CLAUDE-SETUP.md).
- **claude.ai / ChatGPT in a browser** — can't read local files *at all*; use a desktop app, or Path B on a downloaded copy.

So if `claude mcp list` says `✓ Connected` but a chat says *"I can't find changex / upload the file,"* you're talking to a **different Claude than the one you configured** — set it up for that app too. [Why local-only →](docs/LOCAL-ACCESS.md) · [Other apps →](docs/CALL-FROM-YOUR-APP.md)

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

## 👀 Review the changes

`changex seal` prints these with your real paths — or run them yourself:

```bash
changex review report.changex --doc report.tracked.docx --out review.html   # 📄 inline in the doc's outline
changex view   report.changex --doc report.tracked.docx                     # 🌐 live local page (accept/reject)
#  …or just open report.tracked.docx in Word — real native track changes 🖊️
```

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
    review   render an HTML / markdown redline (--doc = inline in the doc's outline)
    view     serve an interactive localhost review page (accept / reject)
    verify   check a .changex hash chain + baseline

  Passive — any model, even offline
    open     snapshot the baseline before anything edits the file
    seal     diff the edited file → reconstruct the tracked changes

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

**You usually don't need it.** `changex view` (zero-install local page) and the single-file HTML report already give the full accept/reject review on every platform. The desktop app just adds a native icon to double-click for non-technical reviewers; it doesn't add features.

<p align="center">
  <a href="https://github.com/ArioMoniri/changex/releases/latest"><img src="docs/assets/btn-mac.svg" height="44" alt="Download macOS .dmg"></a>
  &nbsp;
  <a href="https://github.com/ArioMoniri/changex/releases/latest"><img src="docs/assets/btn-win.svg" height="44" alt="Download Windows .msi"></a>
  &nbsp;
  <a href="https://github.com/ArioMoniri/changex/releases/latest"><img src="docs/assets/btn-linux.svg" height="44" alt="Download Linux .AppImage"></a>
</p>

Installers attach to **[tagged releases](https://github.com/ArioMoniri/changex/releases)**: macOS `.dmg` is **signed + notarized**; Windows `.msi` and Linux `.AppImage`/`.deb` are unsigned. Build/sign details: [docs/CI-AND-SECRETS.md](docs/CI-AND-SECRETS.md).

</details>

---

## 🛟 Troubleshooting

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
