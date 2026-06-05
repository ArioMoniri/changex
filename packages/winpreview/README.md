# ChangeX preview on Windows

Two ways to preview `.changex` journals (and syntax-highlighted source code) on Windows —
both driven by the same `changex preview` engine the macOS Quick Look extension uses.

## 1. Command line / right-click (most reliable)

```powershell
pip install -U "changex[preview]"
changex preview "report.changex" --open      # writes HTML and opens your default browser
```

`changex preview <file>` renders **any** file to self-contained HTML — a tracked-change
redline for `.changex`, syntax-highlighted source for code/text. After running `install.ps1`
(below) you also get a **right-click ▸ "Preview with ChangeX"** entry on `.changex` and code
files that does exactly this — the most dependable Windows preview, no COM/preview-pane
plumbing involved.

## 2. Explorer preview pane (the "Quick Look" experience)

`ChangeXPreview.dll` is a COM **preview handler**: select a file in Explorer with the
Preview pane on (**Alt+P**) and the redline / highlighted source appears inline — no app, no
Space-bar needed (Windows shows previews in the pane rather than a popup).

Install (elevated PowerShell), after `pip install -U "changex[preview]"`:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

Remove:

```powershell
powershell -ExecutionPolicy Bypass -File uninstall.ps1
```

The handler shells out to `changex preview`, so the engine is shared with macOS/Linux and
there's nothing to keep in sync. It associates `.changex` plus the full set of common code
extensions (`.py`, `.js`, `.ts`, `.rs`, `.go`, `.json`, `.yaml`, `.md`, …).

> Requires the .NET Framework 4.8 runtime (built into Windows 10/11) and `changex` on PATH.
