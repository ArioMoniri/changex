# Contributing to ChangeX 🤝

Thanks for your interest! ChangeX is a provenance-first change-tracker for AI document
edits. Bug reports, ideas, docs fixes, and pull requests are all welcome.

By participating you agree to our [Code of Conduct](CODE_OF_CONDUCT.md).

## 🐛 Reporting bugs / ✨ requesting features

Open a [GitHub issue](https://github.com/ArioMoniri/changex/issues). For bugs, please include:
- your OS + Python version (`python --version`) and `changex --version`,
- the exact command / prompt you ran, and what happened vs. what you expected,
- a small sample file if the issue is format-specific (or steps to make one).

## 🧑‍💻 Dev setup

It's a **uv workspace** of three packages (`packages/core`, `packages/mcp`, `packages/api`)
plus the `changex` meta package and a Tauri viewer (`packages/viewer`).

```bash
git clone https://github.com/ArioMoniri/changex && cd changex
uv sync                                   # installs all packages + dev tools into .venv
# …or without uv:
python -m venv .venv && . .venv/bin/activate
pip install -e packages/core -e "packages/mcp[http]" -e packages/api pytest httpx
```

Run the tests:

```bash
pytest -q                  # the full suite (the LibreOffice oracle is deselected by default)
pytest -q -m libreoffice   # the external-engine oracle (needs `soffice` on PATH)
```

Lint / type-check (optional but appreciated):

```bash
ruff check .
mypy packages/core/src/changex_core
```

## 🗂️ Project layout

| Path | What |
|------|------|
| `packages/core` | the engine: canonical model, `.changex` journal, format **adapters**, renderers, CLI |
| `packages/mcp` | the MCP server (stdio + remote HTTP) |
| `packages/api` | FastAPI REST + OpenAPI wrapper |
| `packages/viewer` | optional Tauri desktop viewer |
| `docs/` | architecture, `.changex` format spec, integration & fidelity guides |
| `tests/` | pytest suite |

Adding a new file format? Implement the `DocumentAdapter` interface
(`packages/core/src/changex_core/adapters/base.py`), register the extension in
`adapters/__init__.py`, and add a `tests/test_<fmt>_adapter.py`. The
[architecture](docs/ARCHITECTURE.md) and [.changex format](docs/CHANGEX_FORMAT.md) docs
explain the contracts.

## 🎬 Animated README assets

The README's motion comes from **hand-authored animated SVGs** — `docs/assets/banner.svg` and
`docs/assets/flow.svg`. Their animation lives in a `<style>`/`<animate>` block *inside* the SVG,
and it plays on GitHub **only when the SVG is referenced as an image** (`<img src="…svg">`), not
pasted inline (GitHub sanitizes inline `<svg>`/`<script>` in Markdown). So embed them as images,
keep the animation self-contained, and avoid `<script>` — none is needed.

For the **hosted docs site** (e.g. GitHub Pages), where a real browser runs scripts, you can drop
in richer Lottie animations with the [LottieFiles dotLottie web component](https://github.com/lottiefiles/dotlottie-web):

```html
<!-- a real web page only — GitHub Markdown strips the custom element + script -->
<dotlottie-wc src="https://lottie.host/<id>.lottie" autoplay loop></dotlottie-wc>
<script type="module" src="https://unpkg.com/@lottiefiles/dotlottie-wc@latest/dist/dotlottie-wc.js"></script>
```

(The JS API is `@lottiefiles/dotlottie-web`'s `DotLottie` class on a `<canvas>`; framework
wrappers exist for React/Vue/Svelte/Solid.) To regenerate the per-format screenshots, run
`scripts/make_screenshots.sh` (renders the review HTML, then snapshots each with headless Chrome).

## 🔀 Pull requests

1. Branch off `main`.
2. Keep changes focused; each source file should stay **under 500 lines**, typed, with docstrings.
3. **Add or update tests** — `pytest -q` must pass.
4. Update the relevant docs (e.g. `docs/FIDELITY.md` if you change format coverage).
5. Open the PR with a clear description of *what* and *why*. CI (tests + viewer build) must be green.

## 🧭 Principles

- **Honesty over hype** — never present a reconstructed/degraded result as full provenance.
  The journal is the source of truth; outputs are projections of it.
- **Local-first** — documents never leave the machine; no network calls in the core.
- **Vendor-neutral** — MCP and CLI surfaces work the same across models.

Questions? Open a [discussion or issue](https://github.com/ArioMoniri/changex/issues). 💬
