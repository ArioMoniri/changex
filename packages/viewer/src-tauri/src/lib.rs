//! ChangeX Viewer — Tauri backend.
//!
//! The Rust side is intentionally thin. It exposes three commands to the
//! React frontend:
//!
//! * `load_journal`  — read a `.changex` JSONL file and parse it into a header
//!   plus a list of events (no Python required for plain reading).
//! * `render_review` — shell out to the `changex-core` Python CLI
//!   (`changex review <file> --format html`) so the viewer renders the EXACT
//!   same redline a terminal user would get. The Python core is the sidecar.
//! * `verify_journal` — shell out to `changex verify <file>` for the
//!   tamper-evidence check.
//!
//! All file access is bounded to a single user-selected `.changex` path passed
//! from the frontend (which obtains it through the Tauri dialog plugin).

use std::path::Path;
use std::process::Command;

use serde::Serialize;

/// One parsed line of a `.changex` journal. Kept loose (`serde_json::Value`)
/// so the viewer survives additive schema changes from the core.
#[derive(Serialize)]
pub struct Journal {
    /// The header line (first JSONL record): doc/session/node_id_map metadata.
    pub header: serde_json::Value,
    /// Every subsequent event line, in file (seq) order.
    pub events: Vec<serde_json::Value>,
    /// Absolute path that was loaded, echoed back for the UI.
    pub path: String,
}

/// Result of shelling out to the `changex` CLI sidecar.
#[derive(Serialize)]
pub struct CliResult {
    pub ok: bool,
    pub stdout: String,
    pub stderr: String,
}

/// Resolve the `changex` executable, robust to GUI launches with a minimal PATH.
///
/// A Finder-launched `.app` inherits only a bare PATH (`/usr/bin:/bin:…`), so a plain
/// `Command::new("changex")` fails even when the CLI is installed in Homebrew / uv /
/// pipx. Resolution order: `CHANGEX_BIN` override → common install dirs → the user's
/// **login-shell** PATH (`$SHELL -lc 'command -v changex'`, which sources their profile
/// and sees Homebrew/uv/pyenv) → bare `changex`. Returns `None` only when nothing works.
fn changex_bin() -> Option<String> {
    if let Ok(p) = std::env::var("CHANGEX_BIN") {
        if !p.trim().is_empty() {
            return Some(p);
        }
    }
    let home = std::env::var("HOME").unwrap_or_default();
    let candidates = [
        "/opt/homebrew/bin/changex".to_string(),
        "/usr/local/bin/changex".to_string(),
        format!("{home}/.local/bin/changex"),
        format!("{home}/.cargo/bin/changex"),
    ];
    for c in candidates {
        if Path::new(&c).is_file() {
            return Some(c);
        }
    }
    // Ask a login shell — it sources the user's profile and yields their real PATH.
    let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/zsh".to_string());
    if let Ok(out) = Command::new(shell)
        .args(["-lc", "command -v changex"])
        .output()
    {
        if out.status.success() {
            let p = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if !p.is_empty() && Path::new(&p).exists() {
                return Some(p);
            }
        }
    }
    // Last resort: bare name (resolves when the app was launched from a terminal).
    if Command::new("changex").arg("--version").output().is_ok() {
        return Some("changex".to_string());
    }
    None
}

/// Reject anything that is not a plain existing `.changex` / `.jsonl` file.
fn validate_path(path: &str) -> Result<(), String> {
    let p = Path::new(path);
    if !p.is_file() {
        return Err(format!("not a file: {path}"));
    }
    let ok_suffix = matches!(
        p.extension().and_then(|e| e.to_str()),
        Some("changex") | Some("jsonl")
    );
    if !ok_suffix {
        return Err("expected a .changex or .jsonl journal".into());
    }
    Ok(())
}

/// Read and parse a `.changex` JSONL file into `{header, events}`.
#[tauri::command]
fn load_journal(path: String) -> Result<Journal, String> {
    validate_path(&path)?;
    let text = std::fs::read_to_string(&path).map_err(|e| format!("read failed: {e}"))?;

    let mut lines = text.lines().filter(|l| !l.trim().is_empty());
    let header_line = lines.next().ok_or("empty journal")?;
    let header: serde_json::Value =
        serde_json::from_str(header_line).map_err(|e| format!("bad header line: {e}"))?;

    let mut events = Vec::new();
    for (i, line) in lines.enumerate() {
        let ev: serde_json::Value =
            serde_json::from_str(line).map_err(|e| format!("bad event line {}: {e}", i + 2))?;
        events.push(ev);
    }

    Ok(Journal {
        header,
        events,
        path,
    })
}

/// Run a `changex` subcommand against `path` and capture stdout/stderr.
fn run_changex(args: &[&str]) -> Result<CliResult, String> {
    let bin = changex_bin().ok_or_else(|| {
        "changex CLI not found. Install it — `uv tool install changex` (or `pip install changex`) \
         — then relaunch the app. Searched PATH, /opt/homebrew/bin, /usr/local/bin and ~/.local/bin."
            .to_string()
    })?;
    let output = Command::new(&bin)
        .args(args)
        .output()
        .map_err(|e| format!("failed to launch changex ({bin}): {e}"))?;
    Ok(CliResult {
        ok: output.status.success(),
        stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
        stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
    })
}

/// Render the HTML redline via the Python core: `changex review <path> --format html`.
#[tauri::command]
fn render_review(path: String) -> Result<CliResult, String> {
    validate_path(&path)?;
    run_changex(&["review", &path, "--format", "html"])
}

/// Verify the hash chain via the Python core: `changex verify <path>`.
#[tauri::command]
fn verify_journal(path: String) -> Result<CliResult, String> {
    validate_path(&path)?;
    run_changex(&["verify", &path])
}

/// Manage the macOS Quick Look preview for `.changex` files via the CLI controller
/// (`changex quicklook status|enable|disable`).
#[tauri::command]
fn quicklook(action: String) -> Result<CliResult, String> {
    match action.as_str() {
        "status" | "enable" | "disable" => run_changex(&["quicklook", &action]),
        _ => Err("invalid quicklook action".into()),
    }
}

/// Open the macOS **Full Disk Access** settings pane so the user can grant this app (and
/// the changex sidecar it spawns) access to ~/Downloads/~/Documents/~/Desktop. macOS only.
#[tauri::command]
fn open_security_settings() -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg("x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles")
            .spawn()
            .map(|_| ())
            .map_err(|e| format!("could not open System Settings: {e}"))
    }
    #[cfg(not(target_os = "macos"))]
    {
        Err("Full Disk Access settings are macOS-only.".into())
    }
}

/// Tauri entry point wired from `main.rs`.
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![
            load_journal,
            render_review,
            quicklook,
            open_security_settings,
            verify_journal
        ])
        .run(tauri::generate_context!())
        .expect("error while running ChangeX Viewer");
}
