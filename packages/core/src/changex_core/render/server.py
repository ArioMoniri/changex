"""A localhost-only interactive review server for a ``.changex`` journal.

``changex view`` starts a stdlib :class:`http.server.HTTPServer` bound to
``127.0.0.1`` *only* (never a routable interface) and serves a single-page review
app:

* the HTML redline (reusing :func:`changex_core.render.html.render_html` over the
  journal's live ``active_events``);
* a provenance timeline of **every** op (including reverted ones), filterable by
  model/agent and by ``seq``;
* per-change **accept / reject** controls. Reject calls
  :meth:`Journal.revert`; accept calls :meth:`Journal.unrevert`. Either way the
  page re-fetches and re-renders the redline + timeline live.

Everything is stdlib: :mod:`http.server` for the server, a hand-rolled JSON API,
and a small inline JS/HTML template (no frontend build, no external CDN, no
network egress). All filesystem access goes through ``safe_path`` upstream (the
journal path is sanitized before the server is constructed).
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

from changex_core.journal.events import Event
from changex_core.journal.journal import Journal, JournalError
from changex_core.render.html import render_html

HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _event_payload(event: Event, reverted: bool) -> dict[str, Any]:
    """Serialize one event for the JSON API (redline + provenance fields)."""
    p = event.provenance
    return {
        "op_id": event.op_id,
        "seq": event.seq,
        "kind": event.op.get("kind"),
        "node_id": event.target.node_id,
        "node_kind": event.target.node_kind,
        "reverted": reverted,
        "op": event.op,
        "provenance": {
            "ts": p.ts,
            "agent": p.agent,
            "vendor": p.vendor,
            "turn_id": p.turn_id,
            "rationale": p.rationale,
            "provenance_source": p.provenance_source,
        },
    }


class ReviewState:
    """Holds the live :class:`Journal` and projects it for the API.

    The journal is the single source of truth; the server never caches a stale
    projection — every API call reads ``active_events`` / ``read`` fresh so a
    revert/accept is reflected immediately.
    """

    def __init__(self, journal: Journal) -> None:
        self._journal = journal
        self._lock = threading.Lock()

    @property
    def journal(self) -> Journal:
        return self._journal

    def redline_html(self) -> str:
        with self._lock:
            return render_html(self._journal.active_events(), title="ChangeX review")

    def events_json(self) -> dict[str, Any]:
        """All ops (reverted flagged), plus the distinct model list, for the UI."""
        with self._lock:
            all_events = sorted(self._journal.read(), key=lambda e: e.seq)
            payload = [
                _event_payload(e, self._journal.is_reverted(e.op_id)) for e in all_events
            ]
        models = sorted({(e["provenance"]["agent"] or "unattributed") for e in payload})
        capture_mode = str(self._journal.header.session.get("capture_mode", "active"))
        return {
            "events": payload,
            "models": models,
            "capture_mode": capture_mode,
            "active_count": sum(1 for e in payload if not e["reverted"]),
            "total_count": len(payload),
        }

    def set_reverted(self, op_id: str, reverted: bool) -> dict[str, Any]:
        """Reject (``reverted=True``) or accept (``False``) one op, then re-project."""
        with self._lock:
            if reverted:
                self._journal.revert(op_id)
            else:
                self._journal.unrevert(op_id)
        return self.events_json()


def _page_html(title: str) -> str:
    """The single-page review app (inline CSS + JS; no external resources)."""
    return _PAGE_TEMPLATE.replace("__TITLE__", title)


class _Handler(BaseHTTPRequestHandler):
    """Routes: ``/`` (page), ``/api/events``, ``/api/redline``, ``/api/review``."""

    state: ReviewState  # injected by the server factory
    page_title: str = "ChangeX review"

    # Silence the default stderr request logging (keeps `changex view` clean).
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj: Any, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _send_html(self, html: str, code: int = 200) -> None:
        self._send(code, html.encode("utf-8"), "text/html; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 - http.server contract
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send_html(_page_html(self.page_title))
        elif path == "/api/events":
            self._send_json(self.state.events_json())
        elif path == "/api/redline":
            self._send_json({"html": self.state.redline_html()})
        else:
            self._send_json({"error": "not found"}, code=404)

    def do_POST(self) -> None:  # noqa: N802 - http.server contract
        path = self.path.split("?", 1)[0]
        if path != "/api/review":
            self._send_json({"error": "not found"}, code=404)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
            op_id = str(body["op_id"])
            action = str(body["action"])  # "reject" | "accept"
        except (ValueError, KeyError, TypeError):
            self._send_json({"error": "expected JSON {op_id, action}"}, code=400)
            return
        if action not in ("reject", "accept"):
            self._send_json({"error": "action must be 'reject' or 'accept'"}, code=400)
            return
        try:
            result = self.state.set_reverted(op_id, reverted=(action == "reject"))
        except JournalError as exc:
            self._send_json({"error": str(exc)}, code=400)
            return
        result["redline_html"] = self.state.redline_html()
        self._send_json(result)


def build_server(
    journal: Journal, *, port: int = DEFAULT_PORT, title: str = "ChangeX review"
) -> HTTPServer:
    """Build (but do not start) a localhost-only review server for ``journal``.

    Binds to ``127.0.0.1`` with the given ``port`` (``0`` picks an ephemeral
    free port — used by the smoke test). Returns the :class:`HTTPServer`; the
    caller is responsible for ``serve_forever`` / ``shutdown``.
    """
    state = ReviewState(journal)

    handler = type(
        "_BoundReviewHandler",
        (_Handler,),
        {"state": state, "page_title": title},
    )
    return HTTPServer((HOST, port), handler)


def serve(
    changex_path: str,
    *,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    doc_path: Optional[str] = None,
) -> None:
    """Open ``changex_path`` and serve the review UI until interrupted.

    ``doc_path`` is accepted for parity with the CLI (so the URL/title can name
    the document) but the redline is always projected from the journal, never the
    tracked docx. Prints the localhost URL and (unless ``open_browser`` is
    ``False``) auto-opens the default browser. Blocks on ``serve_forever``.
    """
    journal = Journal.open(changex_path)
    title = "ChangeX review"
    if doc_path:
        from pathlib import Path

        title = f"ChangeX review — {Path(doc_path).name}"
    server = build_server(journal, port=port, title=title)
    actual_port = server.server_address[1]
    url = f"http://{HOST}:{actual_port}/"
    print(f"changex view serving at {url}")
    print(f"  journal: {changex_path}")
    print("  press Ctrl+C to stop")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # pragma: no cover - browser launch is best-effort
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - interactive stop
        pass
    finally:
        server.shutdown()
        server.server_close()


# --------------------------------------------------------------------------- #
# Inline single-page app. No external CDN / build step: all CSS + JS is here.
# --------------------------------------------------------------------------- #
_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  body { font: 14px/1.5 -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; color: #1b1b1b; }
  header { background: #0d1b2a; color: #fff; padding: .8rem 1.2rem; }
  header h1 { font-size: 1.1rem; margin: 0; }
  header .mode { font-size: .8rem; opacity: .8; }
  .wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; padding: 1.2rem; }
  @media (max-width: 900px) { .wrap { grid-template-columns: 1fr; } }
  section { border: 1px solid #e3e3e3; border-radius: 8px; overflow: hidden; }
  section > h2 { font-size: .85rem; text-transform: uppercase; letter-spacing: .04em;
    margin: 0; padding: .6rem .9rem; background: #f6f8fa; border-bottom: 1px solid #e3e3e3; color: #555; }
  .pad { padding: .9rem; }
  .filters { display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; padding: .6rem .9rem;
    border-bottom: 1px solid #eee; background: #fafbfc; }
  .filters label { font-size: .8rem; color: #555; }
  .filters input, .filters select { font: inherit; padding: .2rem .35rem; }
  ins { background: #e6ffed; text-decoration: none; }
  del { background: #ffeef0; }
  .row { border-bottom: 1px solid #f0f0f0; padding: .55rem .9rem; display: flex; gap: .6rem; align-items: flex-start; }
  .row.reverted { opacity: .45; background: #fcfcfc; }
  .row .body { flex: 1; min-width: 0; }
  .row .kind { font-weight: 600; font-size: .8rem; color: #24467a; }
  .row .meta { color: #777; font-size: .75rem; margin-top: .2rem; word-break: break-word; }
  .row .actions { display: flex; gap: .3rem; }
  button { font: inherit; font-size: .78rem; padding: .25rem .6rem; border: 1px solid #ccc;
    border-radius: 5px; background: #fff; cursor: pointer; }
  button.reject { color: #b3261e; border-color: #e0b4b0; }
  button.accept { color: #1a7f37; border-color: #b4ddc0; }
  button.active { background: #0d1b2a; color: #fff; border-color: #0d1b2a; }
  .pill { font-size: .68rem; padding: .05rem .4rem; border-radius: 999px; background: #eef; color: #335; }
  .pill.observed { background: #fff4e5; color: #8a5a00; }
  .counts { font-size: .78rem; color: #555; padding: .4rem .9rem; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="mode" id="mode"></div>
</header>
<div class="wrap">
  <section>
    <h2>Redline (live, from active events)</h2>
    <div class="pad" id="redline">loading…</div>
  </section>
  <section>
    <h2>Provenance timeline</h2>
    <div class="filters">
      <label>model
        <select id="modelFilter"><option value="">all</option></select>
      </label>
      <label>seq &ge; <input id="seqMin" type="number" min="0" style="width:5rem"></label>
      <label>seq &le; <input id="seqMax" type="number" min="0" style="width:5rem"></label>
      <label><input id="showReverted" type="checkbox" checked> show rejected</label>
    </div>
    <div class="counts" id="counts"></div>
    <div id="timeline"></div>
  </section>
</div>
<script>
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

let DATA = { events: [], models: [], capture_mode: "active" };

function opSummary(e) {
  const o = e.op || {};
  switch (o.kind) {
    case "text.insert": return "<ins>" + esc(o.text) + "</ins>";
    case "text.delete": return "<del>" + esc(o.before) + "</del>";
    case "text.replace": return "<del>" + esc(o.before) + "</del> <ins>" + esc(o.after) + "</ins>";
    case "style.change": return "style " + esc(o.before) + " &rarr; <ins>" + esc(o.style) + "</ins>";
    case "node.insert": return "<ins>+ " + esc((o.value||{}).text) + "</ins>";
    case "node.delete": return "<del>&minus; " + esc((o.value||{}).text) + "</del>";
    default: return esc(o.kind);
  }
}

function render() {
  document.getElementById("mode").textContent =
    "capture mode: " + DATA.capture_mode +
    (DATA.capture_mode === "passive" ? " (degraded — provenance reconstructed by diff)" : "");

  const sel = document.getElementById("modelFilter");
  const cur = sel.value;
  sel.innerHTML = '<option value="">all</option>' +
    DATA.models.map(m => '<option value="' + esc(m) + '">' + esc(m) + '</option>').join("");
  sel.value = cur;

  const model = sel.value;
  const showRev = document.getElementById("showReverted").checked;
  const smin = parseInt(document.getElementById("seqMin").value, 10);
  const smax = parseInt(document.getElementById("seqMax").value, 10);

  const rows = DATA.events.filter(e => {
    const m = e.provenance.agent || "unattributed";
    if (model && m !== model) return false;
    if (!showRev && e.reverted) return false;
    if (!isNaN(smin) && e.seq < smin) return false;
    if (!isNaN(smax) && e.seq > smax) return false;
    return true;
  }).map(e => {
    const src = e.provenance.provenance_source;
    const pill = '<span class="pill ' + esc(src) + '">' + esc(src) + '</span>';
    const meta = "seq " + e.seq + " &middot; " + esc(e.node_id) + " &middot; " +
      esc(e.provenance.agent || "unattributed") + " " + pill +
      (e.provenance.rationale ? ' &middot; &ldquo;' + esc(e.provenance.rationale) + '&rdquo;' : "") +
      " &middot; " + esc(e.provenance.ts);
    const btn = e.reverted
      ? '<button class="accept" data-op="' + esc(e.op_id) + '" data-act="accept">accept</button>'
      : '<button class="reject" data-op="' + esc(e.op_id) + '" data-act="reject">reject</button>';
    return '<div class="row' + (e.reverted ? ' reverted' : '') + '">' +
      '<div class="body"><span class="kind">' + esc(e.kind) + '</span> ' + opSummary(e) +
      '<div class="meta">' + meta + '</div></div>' +
      '<div class="actions">' + btn + '</div></div>';
  });
  document.getElementById("timeline").innerHTML = rows.join("") || '<div class="pad">no matching ops</div>';
  document.getElementById("counts").textContent =
    DATA.active_count + " active / " + DATA.total_count + " total ops";

  document.querySelectorAll("button[data-op]").forEach(b => {
    b.onclick = () => review(b.getAttribute("data-op"), b.getAttribute("data-act"));
  });
}

async function loadEvents() {
  DATA = await (await fetch("/api/events")).json();
  render();
  await loadRedline();
}
async function loadRedline() {
  const r = await (await fetch("/api/redline")).json();
  document.getElementById("redline").innerHTML = r.html;
}
async function review(op_id, action) {
  const res = await fetch("/api/review", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({op_id, action})
  });
  if (!res.ok) { alert("review failed"); return; }
  const data = await res.json();
  DATA = { events: data.events, models: data.models, capture_mode: data.capture_mode,
           active_count: data.active_count, total_count: data.total_count };
  render();
  if (data.redline_html) document.getElementById("redline").innerHTML = data.redline_html;
}

["modelFilter","seqMin","seqMax","showReverted"].forEach(id =>
  document.getElementById(id).addEventListener("input", render));
loadEvents();
</script>
</body>
</html>
"""
