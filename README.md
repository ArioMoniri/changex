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

ChangeX captures **every edit an AI makes** to your documents — `.docx` · `.xlsx` · `.csv` · `.pptx` · `.md` · `.doc` — *as it happens*, with **who / what / when / why**. It's not a diff after the fact — it's a live, attributable record you can review and accept or reject. A diff tells you *how two files differ*; ChangeX tells you **what the AI actually did, in order, and why**. 🎯

Works with **any model** 🤖 — Claude, ChatGPT, Gemini, or a local llama — and shows the changes as real Word track-changes 🖊️, a shareable HTML report 📄, or a live local web page 🌐.

<p align="center">
  <a href="https://pypi.org/project/changex/"><img src="docs/assets/btn-install.svg" height="44" alt="uv tool install changex"></a>
  &nbsp;
  <a href="docs/CLAUDE-SETUP.md"><img src="docs/assets/btn-claude.svg" height="44" alt="Use from Claude & any model"></a>
  &nbsp;
  <a href="docs/"><img src="docs/assets/btn-docs.svg" height="44" alt="Read the docs"></a>
</p>

<p align="center">
  <img src="docs/assets/docx.png" alt="A multi-section report in ChangeX — the AI's edits shown inline in the document's own outline, with a who/why change-log" width="760">
  <br><sub><em>A real, multi-section report in ChangeX's default view: every AI edit inline in place, plus a who/why change-log. Hover any change for who &amp; when.</em></sub>
</p>

---

## ⚡ Install

**Step 1 — install the tool:**

```bash
uv tool install changex      # ✅ recommended — isolated, dodges PEP 668
# or:  pipx install changex   ·   pip install changex   ·   zero-install:  uvx changex
```

**Step 2 — (optional) wire it into your AI *once*, at user scope** so it works in every project and never duplicates:

```bash
claude mcp add -s user changex -- changex-mcp
claude mcp list                              # changex should show ✓ Connected
```

### 🔄 Updating (and how to avoid duplicates)

- **Upgrade the tool:** `uv tool upgrade changex` · `pipx upgrade changex` · `pip install -U changex`. The `changex-mcp` binary updates **in place** — your MCP registration keeps working, so there's **nothing to re-add**.
- **Avoid duplicate MCP entries:** register **once** with `-s user` (Step 2). Running `claude mcp add changex …` *without* `-s user` adds a **separate per-directory entry**, so doing it in several folders piles up duplicates. To reset to a single clean entry:
  ```bash
  claude mcp remove changex                    # repeat in each folder you added it to
  claude mcp add -s user changex -- changex-mcp
  ```

> Hitting `externally-managed-environment` (PEP 668), a `pip` cache warning, or an MCP "Failed to connect"? See **[Troubleshooting](#-troubleshooting)** — they're one-liners.

## 🤖 Use it from your AI

With the MCP server registered (Step 2 above), just ask 💬 — for example:

> *"Use changex to open `~/Documents/Q3-report.docx`. Tighten the executive summary, fix the heading levels, and replace the passive voice in section 2 — make every change a **tracked revision** authored by you, save it, then show me a review of what changed."*

The model edits **through** ChangeX (`open_tracked → get_outline → edit → save_tracked`), so every change lands as a real Word revision with full provenance — nothing silently rewritten. You get back exactly the view in the screenshot above. ✅

> 🔐 **Reaching your local files:** this works in **desktop/local** clients — Claude **Desktop/Code**, Cursor, Cline — where `changex-mcp` runs *on your machine* and reads your local docs. A **browser** chat (claude.ai / ChatGPT web) can't see local files; use the desktop app, or the no-tools path below on a downloaded copy. **[Set it up → docs/CLAUDE-SETUP.md](docs/CLAUDE-SETUP.md)** · [why local-only](docs/LOCAL-ACCESS.md)

👉 Per-app setup for **ChatGPT, Gemini, Cursor, Cline, Ollama, LM Studio**: [docs/CALL-FROM-YOUR-APP.md](docs/CALL-FROM-YOUR-APP.md)

## 🪄 No tools? Capture from any model

No MCP, no tool-calling, no SDK — works with offline/local models, a script, or a human. Three steps:

<p align="center">
  <img src="docs/assets/flow.svg" alt="ChangeX flow: open → edit → seal → review" width="820">
</p>

1. **`changex open report.docx`** — snapshot the original.
2. **Let anything edit `report.docx` in place** — Claude, ChatGPT, a local llama, a script, or you.
3. **`changex seal report.docx`** — ChangeX diffs the file against the snapshot and **reconstructs** the changes into `report.changex` + a Word-openable `report.tracked.docx`.

<p align="center">
  <img src="docs/assets/terminal.svg" alt="Terminal: changex open report.docx, edits happen, then changex seal report.docx" width="820">
</p>

This path sees only before-and-after bytes, so it records a **faithful *what-changed*** but **degraded *who/why*** (the agent / turn / prompt are `null`) — and ChangeX says so out loud. Want full provenance (who/when/why per edit)? Use the [MCP path](#-use-it-from-your-ai) above. ⚖️

## 👀 See the changes — your pick

`changex seal` prints these for you with your real paths — or run them yourself on the
`.changex` + tracked `.docx`:

```bash
changex review report.changex --doc report.tracked.docx --out review.html   # 📄 inline in the doc's outline
changex view   report.changex --doc report.tracked.docx                     # 🌐 live local page (accept/reject)
#  …or just open report.tracked.docx in Word — real native track changes 🖊️
```

💡 Paths with spaces need quotes: `changex open "My Report.docx"`.

## 📦 What it tracks

| Format | How changes show up |
|--------|---------------------|
| 📄 `.docx` | **Native Word track changes** — accept/reject right in Word (text, paragraph, style, **run-format**, **paragraph move**) |
| 📊 `.xlsx` / `.csv` | Non-destructive review copy — colored cells, comments, a `Changes` sheet (your original stays untouched) |
| 📽️ `.pptx` | Revision overlay + a generated "Revisions" summary slide |
| 📝 `.md` | Inline HTML redline (Markdown has no native track-changes) |
| 🗂️ `.doc` (legacy) | Auto-converted to `.docx` (LibreOffice), then native Word revisions — best-effort |

Every format also writes a portable **`.changex`** journal — a hash-chained log of each operation with its provenance. Honest per-format limits: [docs/FIDELITY.md](docs/FIDELITY.md). ⚖️

> **Capture vs. review:** live **MCP** capture and the no-tools **`open`/`seal`** path are **docx-only**; the other formats are captured with scripted **`changex track`** (below) or the `changex-core` API. The review surfaces (`review`, `view`, the `.changex` journal) work for every format.

<details>
<summary>🖼️ <b>See it on every format</b> (click to expand)</summary>
<br>

| Markdown — inline redline | CSV — side-by-side redline |
|:--:|:--:|
| <img src="docs/assets/md.png" width="380"> | <img src="docs/assets/csv.png" width="380"> |
| **Excel** — review + provenance | **PowerPoint** — review |
| <img src="docs/assets/xlsx.png" width="380"> | <img src="docs/assets/pptx.png" width="380"> |

</details>

## ✍️ Prompts to copy

Talk to ChangeX in plain language through your AI — the MCP tools do the work. Each prompt below notes what it does:

> **Tighten + restyle** — *"Open `report.docx` with changex. Replace every "utilize" with "use", fix the two run-on sentences in the intro, and bold the section headings — all as tracked revisions. Save and show me the review."*

> **Proofread, one change each** — *"Using changex, proofread `notes.docx` for grammar only. Make each fix a separate tracked change with a one-line rationale, then give me the change-log grouped by paragraph."*

> **Move a section** *(exercises `node.move`)* — *"Open `contract.docx`, move the "Termination" clause to just after "Payment" as a tracked move, and don't touch anything else."*

**What you get back:** native Word revisions plus the inline review shown in the screenshot above — accept/reject each change in Word, in the browser (`changex view`), or in the HTML report.

**Prefer scripted edits (any format, no model)?** Hand `changex track` a small `ops.json` of ops for that one file — e.g. for a spreadsheet:

```json
[
  { "kind": "cell.set", "sheet": "Q4", "ref": "B3", "before": "95", "after": "120", "rationale": "cloud spend rose" },
  { "kind": "formula.set", "sheet": "Q4", "ref": "C3", "before": "=B3*1.1", "after": "=B3*1.15", "rationale": "higher growth assumption" }
]
```

```bash
changex track budget.xlsx ops.json --out budget.tracked.xlsx --changex budget.changex
changex view  budget.changex --doc budget.tracked.xlsx       # review the overlay
```

(For `.docx`, the ops are `text.replace` / `node.insert` / `style.change` / `format.run` / `node.move` addressed by `node_id` — see [docs/CHANGEX_FORMAT.md](docs/CHANGEX_FORMAT.md).)

## 🖥️ The `changex` CLI

Run `changex` (or `changex help`) for the full command list:

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

`changex shell` drops you into a Python REPL with `changex_core` preloaded; `changex --version` prints the version.

## 💻 Desktop app (optional)

ChangeX ships an optional **[Tauri](https://tauri.app)** desktop viewer — a small, double-clickable window over the **same** review UI you get from `changex view`.

**Why it exists:** so non-technical reviewers can open a native app instead of running a terminal command. It wraps the same renderer — it doesn't add review features. **You usually don't need it:** `changex view` (zero-install local page) and the single-file HTML report already give the full accept/reject review on every platform. Reach for the desktop app only if you specifically want an icon to double-click.

<p align="center">
  <a href="https://github.com/ArioMoniri/changex/releases/latest"><img src="docs/assets/btn-mac.svg" height="44" alt="Download macOS .dmg"></a>
  &nbsp;
  <a href="https://github.com/ArioMoniri/changex/releases/latest"><img src="docs/assets/btn-win.svg" height="44" alt="Download Windows .msi"></a>
  &nbsp;
  <a href="https://github.com/ArioMoniri/changex/releases/latest"><img src="docs/assets/btn-linux.svg" height="44" alt="Download Linux .AppImage"></a>
</p>

Installers are attached to **[tagged releases](https://github.com/ArioMoniri/changex/releases)**: the macOS `.dmg` is **signed + notarized**; the Windows `.msi` and Linux `.AppImage`/`.deb` are unsigned (Gatekeeper/SmartScreen may warn). Building/signing details: [docs/CI-AND-SECRETS.md](docs/CI-AND-SECRETS.md).

## 🛟 Troubleshooting

<details open>
<summary><b>MCP server shows <code>✗ Failed to connect</code> (with <code>uvx changex-mcp</code> or <code>npx …</code>)</b></summary>

The first `uvx changex-mcp` / `npx -y …` invocation **downloads the package and all its
dependencies** into a fresh environment, which can take longer than the MCP health-check
timeout — so `claude mcp list` reports *Failed to connect* even though the server is fine.
(That's why a locally-installed binary connects but a `uvx`/`npx` launcher times out.)

**Fix — register the installed binary at user scope** (no cold start, no duplicates):

```bash
claude mcp remove changex                 # drop any old uvx/per-folder entry
claude mcp add -s user changex -- changex-mcp
claude mcp list                           # changex should now show ✓ Connected
```

Prefer the zero-install `uvx` form? **Warm the cache first** so the next launch is instant:
`uv tool install changex-mcp` (or run `uvx changex-mcp` once and let it download, then Ctrl-C).
</details>

<details>
<summary><b><code>WARNING: Cache entry deserialization failed, entry ignored</code> on <code>pip install</code></b></summary>

```text
pip install -U changex --break-system-packages
Requirement already satisfied: changex ... (0.1.0)
WARNING: Cache entry deserialization failed, entry ignored
```

This is a **pip HTTP-cache warning, not a changex failure** — pip found a stale/corrupt entry
in its wheel cache and skipped it. The install still succeeds. To clear it and force a clean
re-fetch:

```bash
python3 -m pip cache purge
python3 -m pip install -U changex --break-system-packages --no-cache-dir
```

If `pip` still reports an older version (e.g. `0.1.0`) afterwards, the newer one may not be on
PyPI yet — see below.
</details>

<details>
<summary><b>PyPI still shows an old version</b></summary>

`pip` can only install what's on PyPI, and a freshly-published version can lag the index CDN by
a few minutes. If `pip install -U changex` keeps landing an older version, give it ~10 min, or
install from source:

```bash
git clone https://github.com/ArioMoniri/changex && cd changex
uv sync     # or: pip install -e packages/core -e "packages/mcp[http]" -e packages/api
```
</details>

<details>
<summary><b><code>error: externally-managed-environment</code> (PEP 668)</b></summary>

Your system Python refuses a global `pip install`. Use an isolated installer instead:
`uv tool install changex` (or `pipx install changex`). If you must use `pip`, add
`--break-system-packages` — but `uv`/`pipx` are cleaner.
</details>

<details>
<summary><b>Legacy <code>.doc</code> won't open / paths with spaces</b></summary>

- **`.doc` (legacy Word)** is converted to `.docx` on ingest via **LibreOffice** — install it and make
  sure `soffice` is on your `PATH`. The conversion is best-effort and lossy for exotic legacy features.
- **Paths with spaces** must be quoted: `changex open "My Report.docx"`.
- **Browser chats** (claude.ai / ChatGPT web) can't read local files — use a desktop client, or
  `open`/`seal` on a downloaded copy. [Why →](docs/LOCAL-ACCESS.md)
</details>

## ℹ️ About

**ChangeX is a provenance-first change tracker for AI document edits.** When a model touches a
document, ChangeX records *what* changed, *in what order*, and *who/why* — as a portable,
hash-chained **`.changex`** journal — and projects that journal onto whatever review surface the
format supports: **native Word track-changes** for `.docx`, and a non-native review overlay for
`.xlsx` / `.csv` / `.pptx` / `.md`. It's **local-first** (documents never leave your machine; no
network calls in the core) and **vendor-neutral** (the MCP and CLI surfaces behave the same across
Claude, ChatGPT, Gemini, and local models).

> **Repository description** *(for the GitHub "About" field):*
> *Provenance-first change tracking for AI document edits — native Word track-changes + a portable, hash-chained `.changex` journal. Works with any model (MCP + CLI). docx · xlsx · csv · pptx · md.*
>
> *Topics:* `track-changes` · `provenance` · `mcp` · `docx` · `ooxml` · `ai` · `llm` · `event-sourcing` · `document-automation` · `python`

Design principles: **honesty over hype** (a reconstructed/degraded result is never presented as
full provenance), **local-first**, and **vendor-neutral**. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for the design.

## 📦 Published packages

All on PyPI (MIT) — `pip install changex` pulls them all:

| Package | What it is |
|---|---|
| [![changex](https://img.shields.io/pypi/v/changex?label=changex&color=3775A9&logo=pypi&logoColor=white)](https://pypi.org/project/changex/) | umbrella — installs the CLI **and** the MCP server |
| [![changex-core](https://img.shields.io/pypi/v/changex-core?label=changex-core&color=3775A9&logo=pypi&logoColor=white)](https://pypi.org/project/changex-core/) | the engine — model, journal, adapters, renderers, CLI |
| [![changex-mcp](https://img.shields.io/pypi/v/changex-mcp?label=changex-mcp&color=3775A9&logo=pypi&logoColor=white)](https://pypi.org/project/changex-mcp/) | the MCP server (stdio + remote HTTP) |
| [![changex-api](https://img.shields.io/pypi/v/changex-api?label=changex-api&color=3775A9&logo=pypi&logoColor=white)](https://pypi.org/project/changex-api/) | FastAPI REST + OpenAPI wrapper |

## 🤝 Contributing

Issues and PRs are welcome! Start with **[CONTRIBUTING.md](CONTRIBUTING.md)** — it covers the
dev setup (`uv sync`), running the tests, and the project layout. Everyone participating is
expected to follow our **[Code of Conduct](CODE_OF_CONDUCT.md)**.

## 🗺️ Dig deeper

📥 [Install](docs/INSTALL.md) · 🛠️ [Claude setup](docs/CLAUDE-SETUP.md) · 🔌 [Integrations](docs/INTEGRATION.md) · 🔐 [Local file access](docs/LOCAL-ACCESS.md) · 🏗️ [Architecture](docs/ARCHITECTURE.md) · 📐 [.changex format](docs/CHANGEX_FORMAT.md) · ⚖️ [Fidelity & limits](docs/FIDELITY.md) · 🔑 [CI & secrets](docs/CI-AND-SECRETS.md)

## 📜 License

[MIT](LICENSE) — © 2026 Ariorad Moniri.
