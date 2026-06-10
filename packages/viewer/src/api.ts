// Bridge to the Tauri backend with a graceful browser fallback.
//
// When running under Tauri the real commands (load_journal / render_review /
// verify_journal) are invoked. When running in a plain browser (e.g. `vite`
// dev preview with no Tauri shell) every call degrades to mock data so the UI
// stays fully explorable.

import type { CliResult, Journal } from "./types";
import { MOCK_JOURNAL } from "./mockJournal";
import { renderRedlineHtml } from "./redline";

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

type InvokeFn = <T>(cmd: string, args?: Record<string, unknown>) => Promise<T>;

async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  // Lazy import so the bundle works in a non-Tauri browser too.
  const mod = await import("@tauri-apps/api/core");
  return (mod.invoke as InvokeFn)<T>(cmd, args);
}

/** Open a native file picker for a .changex journal (Tauri only). */
export async function pickJournalPath(): Promise<string | null> {
  if (!isTauri()) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const picked = await open({
    multiple: false,
    filters: [{ name: "ChangeX journal", extensions: ["changex", "jsonl"] }],
  });
  return typeof picked === "string" ? picked : null;
}

/** Parse a .changex file into {header, events}. Falls back to mock data. */
export async function loadJournal(path: string): Promise<Journal> {
  if (!isTauri()) return { ...MOCK_JOURNAL, path };
  return invoke<Journal>("load_journal", { path });
}

/** The built-in sample journal (no file needed). */
export function loadSample(): Journal {
  return MOCK_JOURNAL;
}

/**
 * Get the HTML redline. Under Tauri this shells out to the Python core CLI
 * (`changex review --format html`) so the viewer shows the exact same output a
 * terminal user gets. In the browser it renders an equivalent redline locally.
 */
export async function renderReview(journal: Journal): Promise<string> {
  if (!isTauri() || journal.path.includes("(mock)")) {
    return renderRedlineHtml(journal);
  }
  const res = await invoke<CliResult>("render_review", { path: journal.path });
  if (!res.ok) {
    // Fall back to the local renderer if the sidecar is unavailable.
    return renderRedlineHtml(journal, res.stderr || "core CLI unavailable; local render");
  }
  return res.stdout;
}

/**
 * Render the tracked document itself with the changes shown INLINE in its own outline (the
 * native document view) via `changex review --doc <doc>`. Tauri only — needs the real .docx.
 */
export async function renderDocument(journal: Journal, docPath: string): Promise<string> {
  if (!isTauri()) {
    return renderRedlineHtml(journal, "document view needs the desktop app + the tracked .docx");
  }
  const res = await invoke<CliResult>("render_document", { path: journal.path, doc: docPath });
  if (!res.ok) throw new Error(res.stderr || "could not render the document view");
  return res.stdout;
}

/** Best-effort: find the tracked document sibling for a journal (Tauri only). */
export async function findTrackedDoc(journal: Journal): Promise<string | null> {
  if (!isTauri()) return null;
  return invoke<string | null>("find_tracked_doc", {
    path: journal.path,
    filename: journal.header?.doc?.filename ?? null,
  });
}

/** Pick the tracked document to show inline (Tauri only). */
export async function pickDocPath(): Promise<string | null> {
  if (!isTauri()) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const picked = await open({
    multiple: false,
    filters: [{ name: "Tracked document", extensions: ["docx"] }],
  });
  return typeof picked === "string" ? picked : null;
}

/** Verify the hash chain via the Python core (Tauri); mock = always ok. */
export async function verifyJournal(journal: Journal): Promise<CliResult> {
  if (!isTauri() || journal.path.includes("(mock)")) {
    return {
      ok: true,
      stdout: `OK: ${journal.path} verifies (${journal.events.length} ops) [local]`,
      stderr: "",
    };
  }
  return invoke<CliResult>("verify_journal", { path: journal.path });
}
