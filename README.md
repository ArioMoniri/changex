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

ChangeX captures **every edit an AI makes** to your documents — `.docx` · `.xlsx` · `.csv` · `.pptx` · `.md` · `.doc` — *as it happens*, with **who / what / when / why**. It's not a diff after the fact — it's a live, attributable record you can review and accept or reject. 🎯

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

```bash
uv tool install changex      # ✅ recommended — isolated, dodges PEP 668
# or:  pipx install changex   ·   pip install changex   ·   zero-install:  uvx changex
```

🔄 **Update later:** `uv tool upgrade changex` · `pipx upgrade changex` · `pip install -U changex`
&nbsp;(MCP via `uvx`? `uvx changex-mcp@latest` always grabs the newest.)

> Hitting `externally-managed-environment` (PEP 668), a `pip` cache warning, or an MCP "Failed to connect"? See **[Troubleshooting](#-troubleshooting)** — most are one-liners.

## 🤖 Use it from your AI

One line wires ChangeX into Claude Code (or any MCP client):

```bash
claude mcp add changex -- changex-mcp     # uses the installed binary — connects instantly
```

Then just ask 💬 — for example:

> *"Use changex to open `~/Documents/Q3-report.docx`. Tighten the executive summary, fix the heading levels, and replace the passive voice in section 2 — make every change a **tracked revision** authored by you, save it, then show me a review of what changed."*

The model edits **through** ChangeX (`open_tracked → get_outline → edit → save_tracked`), so every change lands as a real Word revision with full provenance — nothing silently rewritten. ✅

> 🔐 **Reaching your local files:** this works in **desktop/local** clients — Claude **Desktop/Code**, Cursor, Cline — where `changex-mcp` runs *on your machine* and reads your local docs. A **browser** chat (claude.ai / ChatGPT web) can't see local files; use the desktop app, or the `open`/`seal` path below on a downloaded copy. **[Set it up → docs/CLAUDE-SETUP.md](docs/CLAUDE-SETUP.md)** · [why local-only](docs/LOCAL-ACCESS.md)

👉 Per-app setup for **ChatGPT, Gemini, Cursor, Cline, Ollama, LM Studio**: [docs/CALL-FROM-YOUR-APP.md](docs/CALL-FROM-YOUR-APP.md)

## 🔁 How it works

<p align="center">
  <img src="docs/assets/flow.svg" alt="ChangeX flow: open → edit → seal → review" width="820">
</p>

**No tools? No problem** — the passive path works with offline/local models, or even a human:

```bash
changex open report.docx     # 📸 snapshot the original
#  …anything edits report.docx in place (a model, a script, or you)…
changex seal report.docx     # 🔍 reconstruct the changes → report.changex + report.tracked.docx
```

`open`/`seal` is the **native-to-any-model** path: no tool-calling required, just before-and-after bytes. It records a faithful *what-changed*, but **degraded** *who/why* (the agent/turn/prompt are `null`) — ChangeX says so out loud. Full provenance comes from the live MCP path above. ⚖️

## 👀 See the changes — your pick

`changex seal` prints these for you with your real paths — or run them on the
`.changex` + tracked `.docx`:

```bash
changex review report.changex --doc report.tracked.docx --out review.html   # 📄 inline in the doc's outline
changex view   report.changex --doc report.tracked.docx                     # 🌐 live local page (accept/reject)
#  …or just open report.tracked.docx in Word — real native track changes 🖊️
```

💡 Paths with spaces need quotes: `changex open "My Report.docx"`.

## 📚 Usage guide

| You want to… | Run |
|---|---|
| Let an AI edit a local doc (Claude Desktop/Code) | `claude mcp add changex -- changex-mcp`, then just ask — [setup](docs/CLAUDE-SETUP.md) |
| Track edits from **any** model or a human (docx) | `changex open file.docx` → *(edit it)* → `changex seal file.docx` |
| Apply scripted edits to **any** format | `changex track in.docx ops.json --out tracked.docx --changex s.changex` |
| See changes **inline in the document** | `changex review file.changex --doc file.tracked.docx --out review.html` |
| Review + accept/reject **live** | `changex view file.changex --doc file.tracked.docx` |
| Verify a journal's integrity | `changex verify file.changex --baseline file.docx` |
| List every command / script it | `changex help` · `changex shell` |

## ✍️ Good prompts to copy

Ask in plain language — the MCP tools do the rest. A few that work well:

> *"Open `report.docx` with changex. Replace every instance of "utilize" with "use", fix the two run-on sentences in the intro, and bold the section headings — as tracked revisions. Save and show me the review."*

> *"Using changex, proofread `notes.docx` for grammar only. Make each fix a separate tracked change with a one-line rationale, then give me the change-log grouped by paragraph."*

> *"Open `contract.docx`, move the "Termination" clause to just after "Payment", and flag it as a tracked move. Don't touch anything else."*  ← exercises `node.move`

Prefer scripted edits (any format, no model)? Hand `changex track` a small `ops.json`
of ops for that one file — e.g. for a spreadsheet:

```json
[
  { "kind": "cell.set", "sheet": "Q4", "ref": "B3", "before": "95", "after": "120", "rationale": "cloud spend rose" },
  { "kind": "formula.set", "sheet": "Q4", "ref": "C3", "before": "=B3*1.1", "after": "=B3*1.15", "rationale": "higher growth assumption" }
]
```

```bash
changex track budget.xlsx ops.json --out budget.tracked.xlsx --changex budget.changex
changex view budget.changex --doc budget.tracked.xlsx       # review the overlay
```

(For a `.docx`, the ops would be `text.replace` / `node.insert` / `style.change` / `format.run` / `node.move` addressed by `node_id` — see [docs/CHANGEX_FORMAT.md](docs/CHANGEX_FORMAT.md).)

## 📦 What it tracks

| Format | How changes show up |
|--------|---------------------|
| 📄 `.docx` | **Native Word track changes** — accept/reject right in Word (text, paragraph, style, **run-format**, **paragraph move**) |
| 📊 `.xlsx` / `.csv` | Non-destructive review copy — colored cells, comments, a `Changes` sheet (your original stays untouched) |
| 📽️ `.pptx` | Revision overlay + a generated "Revisions" summary slide |
| 📝 `.md` | Inline HTML redline (Markdown has no native track-changes) |
| 🗂️ `.doc` (legacy) | Auto-converted to `.docx` (LibreOffice), then native Word revisions — best-effort |

Every format also writes a portable **`.changex`** journal — a hash-chained log of each operation with its provenance. Honest per-format limits: [docs/FIDELITY.md](docs/FIDELITY.md). ⚖️

> **Capture vs. review:** live **MCP** capture and the passive **`open`/`seal`** path are **docx-only** today; the other formats are captured with scripted **`changex track`** (or the `changex-core` API). The review surfaces (`review`, `view`, the `.changex` journal) work for every format.

<details>
<summary>🖼️ <b>See it on every format</b> (click to expand)</summary>
<br>

| Markdown — inline redline | CSV — side-by-side redline |
|:--:|:--:|
| <img src="docs/assets/md.png" width="380"> | <img src="docs/assets/csv.png" width="380"> |
| **Excel** — review + provenance | **PowerPoint** — review |
| <img src="docs/assets/xlsx.png" width="380"> | <img src="docs/assets/pptx.png" width="380"> |

</details>

## 🧠 Why not just diff the files?

A diff tells you *how two files differ*. ChangeX tells you **what the AI actually did, in order, and why** — and lets you accept or reject each change. 🔎

## 🆕 What's new

### v0.1.2 *(current)*
- 🛠️ **CI bumped Node 20 → Node 24** in both `ci.yml` and the optional desktop-bundle workflow.
- 📚 **Docs reconciled with the code:** `format.run` and `node.move` are documented as **implemented** (op-schema **v0.3** — nothing reserved), `.md` added to the fidelity matrix, `.doc` marked **best-effort** (LibreOffice), and the **docx-only** scope of MCP/passive capture spelled out — in [FIDELITY.md](docs/FIDELITY.md) and [CHANGEX_FORMAT.md](docs/CHANGEX_FORMAT.md).
- 🤝 Added a **[Code of Conduct](CODE_OF_CONDUCT.md)** (referenced by the README/CONTRIBUTING).
- 🎬 README refresh: an **animated SVG** banner + flow diagram, rounded CTA buttons, an expanded **[Troubleshooting](#-troubleshooting)** section (MCP "Failed to connect" via `uvx`/`npx` cold-start, and the `pip` cache warning), and a `scripts/make_screenshots.sh` pipeline.

### v0.1.1
- 📝 **Markdown (`.md`)** support and **legacy `.doc`** ingest (auto-converted to `.docx` via LibreOffice).
- 🔓 **`format.run`** (run-property revision → native `w:rPrChange`) and **`node.move`** (paragraph move) un-reserved and implemented.
- 📄 **In-document review** — `changex review --doc` renders changes inline in the document's own outline.
- 🔁 Passive `seal` now also emits a Word-openable **tracked `.docx`** and prints the next-step commands.
- 🧰 `changex --version`, `changex help`, and `changex shell` (a Python REPL with `changex_core` preloaded).

### v0.1.0
- 🚀 First release — provenance-first change tracking for **docx** with the **MCP** server, the **xlsx/csv/pptx** adapters, the passive **`open`/`seal`** path, a remote **HTTP MCP** + **REST/OpenAPI** wrapper, the local **`changex view`** review webserver, and one-command install.

## 🛟 Troubleshooting

<details open>
<summary><b>MCP server shows <code>✗ Failed to connect</code> (with <code>uvx changex-mcp</code> or <code>npx …</code>)</b></summary>

The first `uvx changex-mcp` / `npx -y …` invocation **downloads the package and all its
dependencies** into a fresh environment, which can take longer than the MCP health-check
timeout — so `claude mcp list` reports *Failed to connect* even though the server is fine.
(That's why a locally-installed binary connects but a `uvx`/`npx` launcher times out.)

**Fix — point the config at the installed binary** (no cold start):

```bash
claude mcp remove changex                 # drop the uvx entry (run where you added it)
claude mcp add changex -- changex-mcp     # use the installed binary
claude mcp list                           # changex should now show ✓ Connected
```

Prefer the zero-install `uvx` form? **Warm the cache first** so the next launch is instant:

```bash
uv tool install changex-mcp     # (or run `uvx changex-mcp` once and let it download, then Ctrl-C)
```
</details>

<details>
<summary><b><code>WARNING: Cache entry deserialization failed, entry ignored</code> on <code>pip install</code></b></summary>

```text
pip install -U changex --break-system-packages
Requirement already satisfied: changex ... (0.1.0)
WARNING: Cache entry deserialization failed, entry ignored
```

This is a **pip HTTP-cache warning, not a changex failure** — pip found a stale/corrupt entry
in its wheel cache and simply skipped it. The install still succeeds. To clear it (and force a
clean re-fetch):

```bash
python3 -m pip cache purge
python3 -m pip install -U changex --break-system-packages --no-cache-dir
```

If `pip` still reports `Requirement already satisfied: changex ... (0.1.0)` (or any older
version) after that, the newer release **may not be published to PyPI yet** — see below.
</details>

<details>
<summary><b>PyPI still shows an old version (e.g. <code>0.1.0</code>)</b></summary>

`pip` can only install what's on PyPI. If `pip install -U changex` keeps landing an older
version, **the newer one hasn't been published yet** — publishing is a manual step
(`Actions → Publish to PyPI`, or a GitHub Release; see [docs/CI-AND-SECRETS.md](docs/CI-AND-SECRETS.md)).
Until then, install from source:

```bash
git clone https://github.com/ArioMoniri/changex && cd changex
uv sync     # or: pip install -e packages/core -e "packages/mcp[http]" -e packages/api
```
</details>

<details>
<summary><b><code>error: externally-managed-environment</code> (PEP 668)</b></summary>

Your system Python refuses global `pip install`. Use an isolated installer instead:

```bash
uv tool install changex     # or: pipx install changex
```

If you must use `pip`, add `--break-system-packages` (and `--user`) — but `uv`/`pipx` are cleaner.
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
`.xlsx` / `.csv` / `.pptx` / `.md`. It's **local-first** (documents never leave your machine, no
network calls in the core) and **vendor-neutral** (the MCP and CLI surfaces behave the same across
Claude, ChatGPT, Gemini, and local models).

> **Repository description** *(for the GitHub "About" field):*
> *Provenance-first change tracking for AI document edits — native Word track-changes + a portable, hash-chained `.changex` journal. Works with any model (MCP + CLI). docx · xlsx · csv · pptx · md.*
>
> *Suggested topics:* `track-changes` · `provenance` · `mcp` · `docx` · `ooxml` · `ai` · `llm` · `event-sourcing` · `document-automation` · `python`

Design principles: **honesty over hype** (a reconstructed/degraded result is never presented as
full provenance), **local-first**, and **vendor-neutral**. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for the design and [docs/ROADMAP.md](docs/ROADMAP.md) for what's next.

## 📦 Published packages

All published on PyPI (MIT) — `pip install changex` pulls them all:

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

🎬 **Try all formats:** `python scripts/demo_all_formats.py` · 🐚 **Prefer code?** `changex shell` (Python with ChangeX preloaded)

## 📜 License

[MIT](LICENSE) — © 2026 Ariorad Moniri.
