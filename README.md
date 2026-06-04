# 📝 ChangeX

### See *exactly* what an AI changed in your documents — line by line, with receipts.

[![PyPI](https://img.shields.io/pypi/v/changex.svg?logo=pypi&logoColor=white)](https://pypi.org/project/changex/)
[![Python](https://img.shields.io/pypi/pyversions/changex.svg)](https://pypi.org/project/changex/)
[![CI](https://github.com/ArioMoniri/changex/actions/workflows/ci.yml/badge.svg)](https://github.com/ArioMoniri/changex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

ChangeX captures **every edit an AI makes** to your Office files — `.docx` · `.xlsx` · `.csv` · `.pptx` — *as it happens*, with **who / what / when / why**. It's not a diff after the fact — it's a live, attributable record you can review and accept or reject. 🎯

Works with **any model** 🤖 — Claude, ChatGPT, Gemini, or a local llama — and shows the changes as real Word track-changes 🖊️, a shareable HTML report 📄, or a live local web page 🌐.

---

## ⚡ Install

[![Get it on PyPI](https://img.shields.io/badge/pip%20install-changex-3775A9?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/changex/)

```bash
pip install changex          # or:  uv tool install changex   ·   pipx install changex
```

Don't want to install anything? Run it once: `uvx changex --help` 🚀

## 🤖 Use it from your AI

One line wires ChangeX into Claude Code (or any MCP client):

```bash
claude mcp add changex -- uvx changex-mcp
```

Then just ask 💬 — *"Open report.docx with changex, tighten the intro and fix the heading, then save tracked changes."* The model edits **through** ChangeX, so every change is captured with full provenance. ✅

**No tools? No problem** — works with offline/local models, or even a human:

```bash
changex open report.docx     # 📸 snapshot the original
#  …anything edits report.docx in place (a model, a script, or you)…
changex seal report.docx     # 🔍 reconstruct what changed
```

👉 Per-app setup for **ChatGPT, Gemini, Cursor, Cline, Ollama, LM Studio**: [docs/CALL-FROM-YOUR-APP.md](docs/CALL-FROM-YOUR-APP.md)

## 👀 See the changes — your pick

```bash
changex review s.changex --doc tracked.docx --out review.html   # 📄 inline in the doc's own outline
changex view   s.changex --doc tracked.docx                     # 🌐 live local page (accept / reject)
#  …or just open the tracked .docx in Word — real native track changes 🖊️
```

## 📦 What it tracks

| Format | How changes show up |
|--------|---------------------|
| 📄 `.docx` | **Native Word track changes** — accept/reject right in Word |
| 📊 `.xlsx` / `.csv` | Non-destructive review copy — colored cells, comments, a `Changes` sheet (your original stays untouched) |
| 📽️ `.pptx` | Revision overlay + a generated "Revisions" summary slide |

Every format also writes a portable **`.changex`** journal — a hash-chained log of each operation with its provenance. Honest per-format limits: [docs/FIDELITY.md](docs/FIDELITY.md). ⚖️

## 🧠 Why not just diff the files?

A diff tells you *how two files differ*. ChangeX tells you **what the AI actually did, in order, and why** — and lets you accept or reject each change. 🔎

## 🗺️ Dig deeper

📥 [Install](docs/INSTALL.md) · 🔌 [Integrations](docs/INTEGRATION.md) · 🏗️ [Architecture](docs/ARCHITECTURE.md) · 🛣️ [Roadmap](docs/ROADMAP.md) · 📐 [.changex format](docs/CHANGEX_FORMAT.md)

🎬 **Try it on all formats right now:** `python scripts/demo_all_formats.py`

## 📜 License

[MIT](LICENSE) — © 2026 Ario Moniri.
