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

## PyPI publishing — wired (`.github/workflows/publish.yml`)

So that `pip install changex` / `uvx changex` work, the four packages publish to PyPI via
**Trusted Publishing** (OIDC — no token stored). One-time setup on PyPI (only you can do
this — it's your account):

1. Create a free account at [pypi.org](https://pypi.org).
2. For **each** of the four packages, add a *pending publisher*
   (pypi.org → your account → **Publishing** → **Add a pending publisher**) with these
   **exact** values — only the project name differs:

   | Field | Value |
   |-------|-------|
   | **PyPI Project Name** | `changex` — then repeat for `changex-core`, `changex-mcp`, `changex-api` |
   | **Owner** | `ArioMoniri` |
   | **Repository name** | `changex` |
   | **Workflow name** | `publish.yml` |
   | **Environment name** | *(leave blank)* |

3. Publish: create a GitHub **Release** (or run the **Publish to PyPI** workflow via
   *Actions → Run workflow*). `publish.yml` builds + uploads all four. Done —
   `pip install changex` / `uvx changex-mcp` then work for everyone.

Alternative (token instead of Trusted Publishing): create a token at pypi.org → Account →
API tokens, store it as the `PYPI_API_TOKEN` secret, and swap the publish step to use it.
Trusted Publishing is preferred — nothing to store or rotate.
