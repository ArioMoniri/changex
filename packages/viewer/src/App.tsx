import { useCallback, useEffect, useMemo, useState } from "react";
import type { CliResult, Journal } from "./types";
import {
  isTauri,
  loadJournal,
  loadSample,
  pickJournalPath,
  renderReview,
  verifyJournal,
} from "./api";
import { ProvenanceTimeline } from "./components/ProvenanceTimeline";
import { RedlinePanel } from "./components/RedlinePanel";
import { UpdatesPage } from "./components/UpdatesPage";

export default function App() {
  const [journal, setJournal] = useState<Journal | null>(null);
  const [redline, setRedline] = useState<string>("");
  const [rendering, setRendering] = useState(false);
  const [verify, setVerify] = useState<CliResult | null>(null);
  const [selectedSeq, setSelectedSeq] = useState<number | null>(null);
  const [error, setError] = useState<string>("");
  const [showUpdates, setShowUpdates] = useState(false);

  const tauri = isTauri();

  // Whenever a journal loads, render its redline and verify the chain.
  useEffect(() => {
    if (!journal) return;
    let cancelled = false;
    setRendering(true);
    setVerify(null);
    (async () => {
      try {
        const [html, ver] = await Promise.all([
          renderReview(journal),
          verifyJournal(journal),
        ]);
        if (cancelled) return;
        setRedline(html);
        setVerify(ver);
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setRendering(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [journal]);

  const openFile = useCallback(async () => {
    setError("");
    try {
      const path = await pickJournalPath();
      if (!path) return;
      const j = await loadJournal(path);
      setJournal(j);
      setSelectedSeq(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const openSample = useCallback(() => {
    setError("");
    setJournal(loadSample());
    setSelectedSeq(null);
  }, []);

  // Open macOS Full Disk Access settings so the app (and the changex sidecar it spawns)
  // can read files in ~/Downloads/~/Documents/~/Desktop.
  const grantAccess = useCallback(async () => {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("open_security_settings");
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const docName = useMemo(
    () => journal?.header?.doc?.filename ?? journal?.path ?? "—",
    [journal]
  );
  const sessionId = useMemo(
    () => journal?.header?.session?.session_id ?? journal?.header?.doc?.baseline_sha256 ?? "—",
    [journal]
  );

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">CX</span>
          <div>
            <h1>ChangeX Viewer</h1>
            <p className="subtitle">Provenance review for AI document edits</p>
          </div>
        </div>
        <div className="actions">
          <button onClick={openFile} disabled={!tauri} title={tauri ? "" : "Tauri only"}>
            Open .changex…
          </button>
          <button className="ghost" onClick={openSample}>
            Load sample
          </button>
          {tauri && (
            <button className="ghost" onClick={grantAccess} title="Open macOS Full Disk Access settings">
              Grant access
            </button>
          )}
          {tauri && (
            <button
              className="ghost"
              onClick={() => setShowUpdates(true)}
              title="Updates & Quick Look settings"
            >
              Settings
            </button>
          )}
        </div>
      </header>

      {!tauri && (
        <div className="banner">
          Browser preview mode — file picker and the Python sidecar are disabled.
          &nbsp;Use <strong>Load sample</strong>, or run via <code>npm run tauri:dev</code>.
        </div>
      )}
      {error && (
        <div className="banner error">
          {error}
          {tauri && (
            <>
              {" "}
              <button className="ghost" onClick={grantAccess}>
                Grant file access
              </button>
            </>
          )}
        </div>
      )}

      {journal ? (
        <>
          <section className="meta-bar">
            <Meta label="Document" value={docName} />
            <Meta label="Session" value={sessionId} mono />
            <Meta label="Events" value={String(journal.events.length)} />
            <Meta
              label="Verify"
              value={verify ? (verify.ok ? "chain OK" : "chain BROKEN") : "…"}
              tone={verify ? (verify.ok ? "good" : "bad") : undefined}
            />
            <Meta label="Schema" value={journal.header?.op_schema_version ?? "?"} />
          </section>

          <main className="split">
            <section className="pane pane-timeline">
              <h2>Provenance timeline</h2>
              <ProvenanceTimeline
                events={journal.events}
                selectedSeq={selectedSeq}
                onSelect={setSelectedSeq}
              />
            </section>
            <section className="pane pane-redline">
              <h2>Redline</h2>
              <RedlinePanel html={redline} loading={rendering} />
            </section>
          </main>
        </>
      ) : (
        <div className="placeholder">
          <h2>Open a .changex journal to begin</h2>
          <p>
            The viewer renders the same redline as <code>changex review</code> and a
            provenance timeline of every tracked op. Start with the built-in sample.
          </p>
          <button className="ghost" onClick={openSample}>
            Load sample journal
          </button>
        </div>
      )}

      {tauri && showUpdates && <UpdatesPage onClose={() => setShowUpdates(false)} />}
    </div>
  );
}

function Meta({
  label,
  value,
  mono,
  tone,
}: {
  label: string;
  value: string;
  mono?: boolean;
  tone?: "good" | "bad";
}) {
  return (
    <div className="meta-item">
      <span className="meta-label">{label}</span>
      <span className={`meta-value${mono ? " mono" : ""}${tone ? ` ${tone}` : ""}`}>
        {value}
      </span>
    </div>
  );
}
