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

/// Resolve the `changex` executable.
///
/// Order: explicit `CHANGEX_BIN` env override, then `changex` on PATH.
/// Bundling the Python core as a true Tauri sidecar binary is a packaging task
/// (see README); for the scaffold we rely on the dev's installed CLI.
fn changex_bin() -> String {
    std::env::var("CHANGEX_BIN").unwrap_or_else(|_| "changex".to_string())
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
    let output = Command::new(changex_bin())
        .args(args)
        .output()
        .map_err(|e| format!("failed to launch changex CLI ({e}); is changex-core installed?"))?;
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

/// Tauri entry point wired from `main.rs`.
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            load_journal,
            render_review,
            verify_journal
        ])
        .run(tauri::generate_context!())
        .expect("error while running ChangeX Viewer");
}
