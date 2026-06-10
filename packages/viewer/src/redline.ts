// Local HTML renderer — a TypeScript mirror of changex_core.render.html so the viewer can
// render a journal as the same GitKraken-style commit graph without the Python sidecar
// (browser mode, the built-in sample, or when the CLI is unavailable). Each document part is
// its own coloured lane — a "follow line" you can trace through every edit that touched it.

import type { ChangeEvent, Journal, Op } from "./types";

const LANE_COLORS = [
  "#4dd0e1", "#ba68c8", "#ff8a65", "#f06292", "#64b5f6",
  "#81c784", "#ffd54f", "#9575cd", "#4db6ac", "#f48fb1",
];

function esc(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function opBody(op: Op): string {
  const v = (op.value ?? {}) as { text?: string };
  switch (op.kind) {
    case "text.insert": {
      const ins = `<ins>${esc(op.text)}</ins>`;
      return op.before_anchor ? `after &ldquo;${esc(op.before_anchor)}&rdquo;: ${ins}` : ins;
    }
    case "text.delete":
      return `<del>${esc(op.before)}</del>`;
    case "text.replace":
      return `<del>${esc(op.before)}</del> <ins>${esc(op.after)}</ins>`;
    case "style.change":
      return `style ${esc(op.before)} &rarr; <ins>${esc(op.style)}</ins>`;
    case "node.insert":
      return `<ins>+ ${esc(v.text ?? "")}</ins>`;
    case "node.delete":
      return `<del>&minus; ${esc(v.text ?? "")}</del>`;
    default:
      return esc(JSON.stringify(op));
  }
}

function laneColor(name: string): string {
  if (!name) return "#8b91a0";
  let s = 0;
  for (const c of name) s += c.charCodeAt(0);
  return LANE_COLORS[s % LANE_COLORS.length];
}

function initials(name: string): string {
  const parts = name.replace(/[-_]/g, " ").split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function fmtTs(iso: string): [string, string] {
  if (!iso) return ["", ""];
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return [iso, iso];
  const mon = d.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
  const day = String(d.getUTCDate()).padStart(2, "0");
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return [`${mon} ${day}, ${d.getUTCFullYear()} · ${hh}:${mm}`, iso];
}

const CSS = `
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;font:13px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
     color:#e6e8ef;background:#16181d}
.kx-head{padding:16px 20px;border-bottom:1px solid #2a2d36;background:linear-gradient(180deg,#1d2027,#16181d)}
.kx-title{font-size:16px;font-weight:650;color:#f4f6fb;margin:0;display:flex;align-items:center;gap:8px}
.kx-title .dot{width:9px;height:9px;border-radius:50%;background:#4dd0e1}
.kx-sub{margin:6px 0 0;color:#9aa0ad;font-size:12px;display:flex;flex-wrap:wrap;gap:6px 14px}
.kx-sub b{color:#c7ccd6;font-weight:600}.kx-sub code{font:11px ui-monospace,Menlo,monospace;color:#9aa0ad}
.kx-authors{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.kx-legend{display:flex;align-items:center;gap:7px;margin-top:9px;font-size:11px;color:#7f8696}
.kx-legend svg{flex:none;color:#5a5f6b}
.kx-chip{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:#cfd4de;background:#23262e;
         border:1px solid #2f333d;border-radius:999px;padding:2px 9px 2px 3px}
.av{width:18px;height:18px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;
    font-size:9px;font-weight:700;color:#10121a}
.note{color:#febc2e;font-size:11px;padding:8px 20px;border-bottom:1px solid #2a2d36}
ol.kx{list-style:none;margin:0;padding:6px 0 24px}
li.commit{display:grid;grid-template-columns:var(--rw,46px) 1fr;align-items:stretch}
.rail{position:relative;min-height:44px}
.ln{position:absolute;width:2px;transform:translateX(-1px)}
.node{position:absolute;top:13px;width:13px;height:13px;border-radius:50%;transform:translateX(-50%);
      border:3px solid #16181d;background:var(--c);box-shadow:0 0 0 1px rgba(0,0,0,.25)}
.card{padding:9px 16px 13px 4px;border-bottom:1px solid #1f2229}
li.commit:hover .card{background:#1b1e25}
.r1{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.hash{font:11px ui-monospace,Menlo,monospace;color:#10121a;background:var(--c);border-radius:4px;padding:1px 6px;font-weight:600}
.kind{font:11px ui-monospace,Menlo,monospace;color:#aeb4c0;background:#23262e;border:1px solid #2f333d;border-radius:4px;padding:1px 6px}
.part{font:11px ui-monospace,Menlo,monospace;color:#7f8696}
.diff{margin:6px 0 5px;color:#d7dbe3;word-break:break-word}
ins{background:rgba(63,185,80,.22);color:#7ee787;text-decoration:none;border-radius:3px;padding:0 3px}
del{background:rgba(248,81,73,.20);color:#ff9d96;border-radius:3px;padding:0 3px}
.m{display:flex;align-items:center;gap:8px;color:#8b91a0;font-size:11px;flex-wrap:wrap}
.who{display:inline-flex;align-items:center;gap:5px;color:#c7ccd6}
.rationale{color:#9aa0ad;font-style:italic}.empty{padding:28px 20px;color:#8b91a0}
@media(prefers-color-scheme:light){
  body{color:#1f2329;background:#fff}
  .kx-head{background:linear-gradient(180deg,#f6f7f9,#fff);border-color:#e6e8ec}
  .kx-title{color:#11151a}.kx-sub{color:#6b7280}.kx-sub b{color:#374151}
  .kx-chip{background:#f1f3f5;border-color:#e2e5ea;color:#374151}
  .node{border-color:#fff}.card{border-color:#eef0f3}li.commit:hover .card{background:#f8f9fb}
  .kind{background:#f1f3f5;border-color:#e2e5ea;color:#4b5563}.part{color:#9aa1ad}
  .diff{color:#1f2329}ins{color:#1a7f37}del{color:#b42318}.m{color:#6b7280}.who{color:#374151}
}
`.trim();

/** Render the journal as a self-contained GitKraken-style commit graph (HTML document). */
export function renderRedlineHtml(journal: Journal, note?: string): string {
  // Chronological: oldest commit first (sort on ts, seq as tiebreak).
  const evs = [...(journal.events ?? [])].sort(
    (a, b) => (a.ts ?? "").localeCompare(b.ts ?? "") || a.seq - b.seq
  );
  const partOf = evs.map((ev) => ev.target?.node_id || ev.target?.path || "doc");
  const order: string[] = [];
  for (const k of partOf) if (!order.includes(k)) order.push(k);
  const partColor: Record<string, string> = {};
  order.forEach((k, i) => (partColor[k] = LANE_COLORS[i % LANE_COLORS.length]));
  const span: Record<string, [number, number]> = {};
  partOf.forEach((k, r) => {
    if (!(k in span)) span[k] = [r, r];
    else span[k][1] = r;
  });
  const laneOf: Record<string, number> = {};
  order.forEach((k, i) => (laneOf[k] = i));
  const nLanes = Math.max(1, order.length);
  const lanesParts: Record<number, Array<[string, number, number]>> = {};
  for (const k of order) lanesParts[laneOf[k]] = [[k, span[k][0], span[k][1]]];
  const laneX = (lane: number) => 14 + lane * 20;
  const railW = laneX(nLanes - 1) + 28;

  const authors: Record<string, number> = {};
  let firstTs = "";
  let lastTs = "";
  const rows = evs
    .map((ev: ChangeEvent, r: number) => {
      const agent = ev.provenance?.agent || "unknown";
      authors[agent] = (authors[agent] ?? 0) + 1;
      if (!firstTs) firstTs = ev.ts;
      lastTs = ev.ts;
      const [human, raw] = fmtTs(ev.ts);
      const myPart = partOf[r];
      const myLane = laneOf[myPart];
      const pcolor = partColor[myPart];

      const cell: string[] = [];
      for (let lane = 0; lane < nLanes; lane++) {
        const occ = (lanesParts[lane] ?? []).find((p) => p[1] <= r && r <= p[2]);
        if (!occ) continue;
        const x = laneX(lane);
        const col = partColor[occ[0]];
        const isFirst = r === occ[1];
        const isLast = r === occ[2];
        if (isFirst && isLast) {
          /* lone commit — dot only */
        } else if (isFirst) {
          cell.push(`<i class="ln" style="left:${x}px;top:20px;bottom:0;background:${col}"></i>`);
        } else if (isLast) {
          cell.push(`<i class="ln" style="left:${x}px;top:0;height:20px;background:${col}"></i>`);
        } else {
          cell.push(`<i class="ln" style="left:${x}px;top:0;bottom:0;background:${col}"></i>`);
        }
        if (lane === myLane) {
          cell.push(`<span class="node" style="left:${x}px;background:${pcolor}"></span>`);
        }
      }

      const short = (ev.hash ?? "").slice(0, 7) || `seq${ev.seq}`;
      const acolor = laneColor(agent);
      const partLabel = ev.target?.path || ev.target?.node_id || "";
      const rationale = ev.provenance?.rationale
        ? `<span class="rationale">&ldquo;${esc(ev.provenance.rationale)}&rdquo;</span>`
        : "";
      return (
        `<li class="commit" style="--c:${pcolor}">` +
        `<div class="rail">${cell.join("")}</div>` +
        `<div class="card"><div class="r1"><span class="hash">${esc(short)}</span>` +
        `<span class="kind">${esc(ev.op.kind)}</span><span class="part">${esc(partLabel)}</span></div>` +
        `<div class="diff">${opBody(ev.op)}</div>` +
        `<div class="m"><span class="who"><span class="av" style="background:${acolor}">` +
        `${esc(initials(agent))}</span>${esc(agent)}</span>` +
        `<span title="${esc(raw)}">${esc(human)}</span>` +
        `${rationale ? " &middot; " + rationale : ""}</div></div></li>`
      );
    })
    .join("");

  const doc = journal.header?.doc;
  const title = esc(doc?.filename ?? journal.path);
  const sub: string[] = [`<b>${evs.length}</b> change${evs.length === 1 ? "" : "s"}`];
  sub.push(`<b>${order.length}</b> part${order.length === 1 ? "" : "s"}`);
  if (doc?.format) sub.push(`<b>${esc(doc.format)}</b>`);
  if (firstTs) {
    const [a] = fmtTs(firstTs);
    const [b] = fmtTs(lastTs);
    sub.push(a === b ? a : `${a} → ${b}`);
  }
  if (doc?.baseline_sha256) {
    sub.push(`baseline <code>${esc(String(doc.baseline_sha256).slice(0, 10))}</code>`);
  }

  const chips = Object.entries(authors)
    .sort((x, y) => y[1] - x[1])
    .map(
      ([a, n]) =>
        `<span class="kx-chip"><span class="av" style="background:${laneColor(a)}">` +
        `${esc(initials(a))}</span>${esc(a)} · ${n}</span>`
    )
    .join("");

  const noteHtml = note ? `<div class="note">note: ${esc(note)}</div>` : "";
  const legend = rows
    ? '<div class="kx-legend"><svg width="14" height="22" viewBox="0 0 14 22" aria-hidden="true">' +
      '<line x1="7" y1="3" x2="7" y2="19" stroke="currentColor" stroke-width="2"/>' +
      '<circle cx="7" cy="5" r="3" fill="#4dd0e1"/><circle cx="7" cy="17" r="3" fill="#4dd0e1"/></svg>' +
      "Each lane is a document part — a line follows that part through its edits</div>"
    : "";
  const head =
    `<div class="kx-head"><h1 class="kx-title"><span class="dot"></span>${title}</h1>` +
    `<div class="kx-sub">${sub.join(" &middot; ")}</div>` +
    (chips ? `<div class="kx-authors">${chips}</div>` : "") +
    legend +
    "</div>";
  const graph = rows
    ? `<ol class="kx" style="--rw:${railW}px">${rows}</ol>`
    : '<div class="empty">No changes recorded.</div>';
  return (
    `<!doctype html><html><head><meta charset="utf-8">` +
    `<meta name="viewport" content="width=device-width,initial-scale=1">` +
    `<style>${CSS}</style></head><body>${head}${noteHtml}${graph}</body></html>`
  );
}
