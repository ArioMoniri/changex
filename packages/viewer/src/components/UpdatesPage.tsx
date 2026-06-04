import { useCallback, useEffect, useState } from "react";

// The Tauri updater/process plugins are imported lazily so a browser build never
// touches them; the page is only mounted inside the Tauri app anyway.

type Phase =
  | { k: "checking" }
  | { k: "uptodate" }
  | { k: "available"; version: string; notes: string }
  | { k: "downloading"; version: string; pct: number }
  | { k: "ready"; version: string }
  | { k: "error"; message: string };

interface PendingUpdate {
  version: string;
  body?: string;
  downloadAndInstall: (onEvent: (e: DownloadEvent) => void) => Promise<void>;
}

interface DownloadEvent {
  event: "Started" | "Progress" | "Finished";
  data?: { contentLength?: number; chunkLength?: number };
}

export function UpdatesPage({ onClose }: { onClose: () => void }) {
  const [version, setVersion] = useState<string>("…");
  const [phase, setPhase] = useState<Phase>({ k: "checking" });
  const [pending, setPending] = useState<PendingUpdate | null>(null);
  const [qlMsg, setQlMsg] = useState<string>("");

  useEffect(() => {
    import("@tauri-apps/api/app")
      .then((m) => m.getVersion())
      .then(setVersion)
      .catch(() => setVersion("?"));
  }, []);

  // Quick Look (Finder preview) control — delegates to `changex quicklook`.
  const setQuickLook = useCallback(async (action: "status" | "enable" | "disable") => {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const res = (await invoke("quicklook", { action })) as { stdout: string; stderr: string };
      setQlMsg((res.stdout + res.stderr).trim());
    } catch (e) {
      setQlMsg(String(e));
    }
  }, []);
  useEffect(() => {
    setQuickLook("status");
  }, [setQuickLook]);

  const check = useCallback(async () => {
    setPhase({ k: "checking" });
    setPending(null);
    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const up = (await check()) as PendingUpdate | null;
      if (!up) {
        setPhase({ k: "uptodate" });
        return;
      }
      setPending(up);
      setPhase({ k: "available", version: up.version, notes: up.body ?? "" });
    } catch (e) {
      setPhase({ k: "error", message: String(e) });
    }
  }, []);

  const install = useCallback(async () => {
    if (!pending) return;
    try {
      let total = 0;
      let got = 0;
      setPhase({ k: "downloading", version: pending.version, pct: 0 });
      await pending.downloadAndInstall((e) => {
        if (e.event === "Started") {
          total = e.data?.contentLength ?? 0;
        } else if (e.event === "Progress") {
          got += e.data?.chunkLength ?? 0;
          const pct = total ? Math.round((got / total) * 100) : 0;
          setPhase({ k: "downloading", version: pending.version, pct });
        }
      });
      setPhase({ k: "ready", version: pending.version });
      const { relaunch } = await import("@tauri-apps/plugin-process");
      await relaunch();
    } catch (e) {
      setPhase({ k: "error", message: String(e) });
    }
  }, [pending]);

  useEffect(() => {
    check();
  }, [check]);

  return (
    <div className="updates-overlay" role="dialog" aria-label="Updates">
      <div className="updates-card">
        <div className="updates-head">
          <h2>Settings</h2>
          <button className="ghost" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="updates-current">
          Installed&nbsp;<strong>v{version}</strong>
        </p>

        {phase.k === "checking" && <p className="updates-line">Checking for updates…</p>}
        {phase.k === "uptodate" && (
          <p className="updates-line good">You're on the latest version ✓</p>
        )}
        {phase.k === "available" && (
          <div className="updates-avail">
            <p className="updates-line">
              <strong>v{phase.version}</strong> is available.
            </p>
            {phase.notes && <pre className="updates-notes">{phase.notes}</pre>}
            <button onClick={install}>Download &amp; install</button>
          </div>
        )}
        {phase.k === "downloading" && (
          <div className="updates-line">
            <p>
              Downloading v{phase.version}… {phase.pct}%
            </p>
            <div className="updates-bar">
              <div className="updates-bar-fill" style={{ width: `${phase.pct}%` }} />
            </div>
          </div>
        )}
        {phase.k === "ready" && (
          <p className="updates-line good">Installed v{phase.version} — restarting…</p>
        )}
        {phase.k === "error" && <p className="updates-line bad">Update failed: {phase.message}</p>}

        <hr className="updates-rule" />

        <h3 className="updates-h3">Quick Look — Finder preview for .changex</h3>
        {qlMsg && <pre className="updates-notes">{qlMsg}</pre>}
        <div className="updates-ql-row">
          <button onClick={() => setQuickLook("enable")}>Enable</button>
          <button className="ghost" onClick={() => setQuickLook("disable")}>
            Disable
          </button>
        </div>

        <div className="updates-foot">
          <button
            className="ghost"
            onClick={check}
            disabled={phase.k === "checking" || phase.k === "downloading"}
          >
            Check for updates
          </button>
        </div>
      </div>
    </div>
  );
}
