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

Quick reference:

| Secret | What it is |
|--------|------------|
| `APPLE_CERTIFICATE` | base64 of your **Developer ID Application** cert as a `.p12` |
| `APPLE_CERTIFICATE_PASSWORD` | the password you set when exporting the `.p12` |
| `APPLE_SIGNING_IDENTITY` | e.g. `Developer ID Application: Ariorad Moniri (TEAMID)` |
| `APPLE_ID` | your Apple Developer account email |
| `APPLE_PASSWORD` | an Apple **app-specific password** (not your login password) |
| `APPLE_TEAM_ID` | your 10-char Team ID |

**Step-by-step — how to get each (do these once):**

1. **Join the Apple Developer Program** (~$99/yr): https://developer.apple.com/programs/ →
   *Enroll*. You need this before any of the below exists.
2. **`APPLE_TEAM_ID`** — https://developer.apple.com/account → **Membership details** →
   copy the 10-character **Team ID** (e.g. `A1B2C3D4E5`).
3. **Create the signing certificate** — in **Xcode** (easiest): *Settings → Accounts →*
   select your team *→ Manage Certificates → +  → "Developer ID Application"*. (Or via the
   web: developer.apple.com/account → *Certificates → + → Developer ID Application*, follow
   the CSR steps.) It installs into **Keychain Access**.
4. **`APPLE_SIGNING_IDENTITY`** — open **Keychain Access → My Certificates**, find
   *"Developer ID Application: Your Name (TEAMID)"* and copy that full string.
5. **Export the cert → `.p12`** — in Keychain Access, right-click that certificate →
   **Export** → format **Personal Information Exchange (.p12)** → set a password. That
   password **is `APPLE_CERTIFICATE_PASSWORD`**.
6. **`APPLE_CERTIFICATE`** — base64-encode the `.p12` and copy it:
   ```bash
   base64 -i developer_id.p12 | pbcopy   # now paste into the GitHub secret
   ```
7. **`APPLE_ID`** — the email of your Apple Developer account.
8. **`APPLE_PASSWORD`** — an **app-specific password** (the notary service needs this, not
   your real password): https://account.apple.com → **Sign-In & Security → App-Specific
   Passwords → +** → name it "changex notarize" → copy the `xxxx-xxxx-xxxx-xxxx` value.

Then add each as **GitHub → repo → Settings → Secrets and variables → Actions → New
repository secret** (exact names from the table). Run **Actions → Desktop bundle (Tauri) →
Run workflow**, and it produces a signed, notarized `.dmg`.

> Reminder: this is **optional** — only worth it if you want notarized installers for
> non-technical users. `changex view` already gives the review UI with no install.

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

### If the pending-publisher form errors ("temporarily unavailable") — use an API token

PyPI **rate-limits pending-publisher creation** and has a known monorepo rough edge
([warehouse#16920](https://github.com/pypi/warehouse/issues/16920)), so adding 4 in a row
often fails with a generic "outage" message even though PyPI is up. The token route skips
that form entirely and `publish.yml` already supports it (auto-detected):

1. pypi.org → **Account settings** → **API tokens** → **Add API token**.
   - Name: `changex-github` (anything). **Scope: "Entire account"** — required for the
     *first* upload, since the projects don't exist yet to scope to.
   - Copy the token (starts with `pypi-…`).
2. GitHub → repo **Settings → Secrets and variables → Actions → New repository secret**:
   - Name: `PYPI_API_TOKEN`  ·  Value: the `pypi-…` token.
3. Run **Actions → Publish to PyPI → Run workflow** (or cut a Release). It builds + uploads
   all four. No pending publishers needed.
4. *(optional, after first publish)* the projects now exist — you can delete the
   account-scoped token and switch to per-project tokens or add Trusted Publishers to the
   existing projects for tighter security, then remove the `PYPI_API_TOKEN` secret.

You only need **one** account-scoped token for all four packages.
