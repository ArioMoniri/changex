# ChangeX Viewer

A **Tauri v2 + React/TypeScript** desktop app for reviewing ChangeX provenance
journals. It loads a `.changex` file and shows two synchronized panes:

- **Provenance timeline** — every tracked op in order: what changed, on which
  node, by which agent/vendor, when, and (if declared) why, with an
  `observed` / `declared` provenance label per event.
- **Redline** — the same HTML redline `changex review` produces, rendered in a
  sandboxed iframe.

The Rust backend runs the `changex-core` Python CLI as a **sidecar** for
`render_review` and `verify_journal`; plain JSONL reading is done natively in
Rust. In a non-Tauri browser the UI degrades to a built-in **sample journal**
and a local TypeScript redline renderer, so it stays fully explorable without
the desktop shell.

## Prerequisites

- Node.js 18+ and npm
- Rust toolchain (`rustup`) — see https://v2.tauri.app/start/prerequisites/
- Platform webview deps (macOS: Xcode CLT; Linux: `webkit2gtk`; Windows: WebView2)
- `changex-core` installed so the `changex` CLI is on `PATH` (for the live
  redline/verify sidecar):

  ```bash
  pip install -e ../core      # from packages/viewer
  changex --help
  ```

  Override the binary with the `CHANGEX_BIN` env var if it is not on `PATH`.

## Run

```bash
cd packages/viewer
npm install

# Desktop app (Tauri) — full functionality incl. file picker + Python sidecar:
npm run tauri:dev

# Browser preview only (sample data + local renderer, no sidecar):
npm run dev          # http://localhost:5173
```

## Build

```bash
npm run build          # type-check + Vite bundle into dist/
npm run tauri:build    # native installer (.dmg/.app, .msi, .deb/.AppImage)
```

## How it talks to the core

| Frontend call    | Tauri command    | Backend behavior                                  |
| ---------------- | ---------------- | ------------------------------------------------- |
| `loadJournal`    | `load_journal`   | reads `.changex` JSONL natively, returns header + events |
| `renderReview`   | `render_review`  | runs `changex review <path> --format html`        |
| `verifyJournal`  | `verify_journal` | runs `changex verify <path>`                      |

All three validate that the path is an existing `.changex`/`.jsonl` file before
acting. The file path is chosen through the Tauri dialog plugin.

## Layout

```
packages/viewer
├── package.json              # npm scripts + React/Tauri deps
├── index.html                # Vite entry
├── vite.config.ts            # dev server on :5173, dist build
├── tsconfig*.json            # strict TS config
├── src/
│   ├── main.tsx              # React bootstrap
│   ├── App.tsx               # two-pane shell + load/verify wiring
│   ├── api.ts                # Tauri bridge with browser fallback
│   ├── redline.ts            # local HTML redline (mirror of core renderer)
│   ├── types.ts              # .changex journal types
│   ├── mockJournal.ts        # built-in sample session
│   ├── styles.css            # app styles
│   └── components/
│       ├── ProvenanceTimeline.tsx
│       └── RedlinePanel.tsx
└── src-tauri/
    ├── Cargo.toml            # tauri 2 + shell/dialog plugins
    ├── tauri.conf.json       # window + bundle config
    ├── build.rs
    ├── capabilities/default.json
    └── src/
        ├── main.rs           # thin entry -> lib::run()
        └── lib.rs            # load_journal / render_review / verify_journal
```

## Status

Scaffold. The viewer is an **optional** review surface — the MVP review path is
the native tracked `.docx` (Word renders accept/reject) plus `changex review`
HTML. Bundling the Python core as a true notarized Tauri sidecar binary is a
follow-up packaging task; today it shells out to the installed `changex` CLI.

> Note: `src-tauri/icons/icon.png` is a placeholder. Replace it with real app
> icons (e.g. `cargo tauri icon path/to/logo.png`) before producing a release
> bundle.
