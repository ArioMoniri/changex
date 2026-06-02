# CI & repository secrets

Two workflows live in `.github/workflows/`:

| Workflow | Trigger | Needs secrets? |
|----------|---------|----------------|
| [`ci.yml`](../.github/workflows/ci.yml) — tests + **LibreOffice accept/reject oracle** + viewer build | every push / PR to `main` | **No** |
| [`release-desktop.yml`](../.github/workflows/release-desktop.yml) — **Tauri** desktop bundle (optional) | manual (`workflow_dispatch`) or a `v*` tag | Only to **sign/notarize** (see below) |

## CI (`ci.yml`) — no secrets required ✅

Runs on Linux. It installs LibreOffice and runs the external-engine oracle
(`pytest -m libreoffice`) that drives a real Accept-All / Reject-All and compares the
result to ChangeX's output — the strongest possible round-trip check, and the one that
can't run headless on macOS. It also runs the portable suite (`pytest -q`) and builds
the viewer frontend. Nothing to configure; it's green out of the box.

## Desktop bundle (`release-desktop.yml`) — optional, secret-gated

> **Recommendation: you probably don't need this.** `changex view` (zero-install local
> webserver) + the single-file HTML report already deliver the review UI cross-platform.
> The Tauri app only adds a double-clickable icon, and it isn't self-contained yet (it
> shells out to a `changex` CLI on PATH rather than bundling Python). Only invest in the
> signing certs below if you specifically want notarized installers for non-technical users.

With **no** secrets set, the workflow still builds **unsigned** bundles (usable locally;
macOS Gatekeeper will warn). Add these repo secrets to get signed + notarized builds —
**Settings → Secrets and variables → Actions → New repository secret**:

### macOS notarization (Apple Developer Program, ~$99/yr required)
| Secret | What it is / how to get it |
|--------|----------------------------|
| `APPLE_CERTIFICATE` | base64 of your **Developer ID Application** cert exported as `.p12`: `base64 -i cert.p12 \| pbcopy` |
| `APPLE_CERTIFICATE_PASSWORD` | the password you set when exporting the `.p12` |
| `APPLE_SIGNING_IDENTITY` | e.g. `Developer ID Application: Your Name (TEAMID)` (from Keychain Access) |
| `APPLE_ID` | your Apple Developer account email |
| `APPLE_PASSWORD` | an **app-specific password** (appleid.apple.com → Sign-In and Security → App-Specific Passwords), *not* your login password |
| `APPLE_TEAM_ID` | your 10-char Team ID (Apple Developer → Membership) |

### Windows code signing (optional, needs a code-signing cert)
| Secret | What it is |
|--------|------------|
| `WINDOWS_CERTIFICATE` | base64 of your code-signing `.pfx` |
| `WINDOWS_CERTIFICATE_PASSWORD` | the `.pfx` password |

(Wire these into `tauri.conf.json > bundle > windows` or the tauri-action env when you
adopt Windows signing — left out of the default workflow since most users won't need it.)

Linux builds are not signed (AppImage/`.deb` are distributed as-is).

## Not yet wired: PyPI publishing (so `pip install changex` actually works)

The README's `pip install changex` / `uvx changex` commands assume the packages are on
PyPI — they aren't published yet. To enable them, add a publish workflow plus **one** of:

- **PyPI Trusted Publishing (recommended, no secret):** configure a trusted publisher on
  PyPI for this repo/workflow and use `id-token: write` — no token stored at all; or
- **`PYPI_API_TOKEN`** secret — a project-scoped token from pypi.org → Account settings →
  API tokens.

Say the word and I'll add the publish workflow + register the four packages
(`changex`, `changex-core`, `changex-mcp`, `changex-api`).
