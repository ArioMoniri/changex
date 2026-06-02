// Local HTML redline renderer — a TypeScript mirror of changex_core.render.html
// so the viewer can render a journal without the Python sidecar (browser mode
// or when the CLI is unavailable). The Tauri path prefers the real core output.

import type { ChangeEvent, Journal, Op } from "./types";

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

function provLine(ev: ChangeEvent): string {
  const p = ev.provenance;
  const bits = [`seq ${ev.seq}`, esc(ev.target.node_id)];
  if (p.agent) bits.push(esc(p.agent));
  if (p.vendor) bits.push(esc(p.vendor));
  bits.push(esc(p.provenance_source));
  if (p.rationale) bits.push(`&ldquo;${esc(p.rationale)}&rdquo;`);
  bits.push(esc(p.ts));
  return bits.join(" &middot; ");
}

const CSS = `
body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:1.2rem;color:#1a1a1a;}
h1{font-size:1.3rem;}
.op{padding:.4rem .6rem;border-left:3px solid #ddd;margin:.3rem 0;}
ins{background:#e6ffed;text-decoration:none;}
del{background:#ffeef0;}
.meta{color:#666;font-size:.8rem;}
.kind{font-weight:600;}
.note{color:#9a6700;font-size:.8rem;margin:.4rem 0;}
`.trim();

/** Render a full standalone HTML redline document for the journal. */
export function renderRedlineHtml(journal: Journal, note?: string): string {
  const title = `ChangeX review — ${esc(journal.header?.doc?.filename ?? journal.path)}`;
  const rows = journal.events
    .map(
      (ev) =>
        `<div class="op"><span class="kind">${esc(ev.op.kind)}</span> ${opBody(
          ev.op
        )}<div class="meta">${provLine(ev)}</div></div>`
    )
    .join("");
  const noteHtml = note ? `<div class="note">note: ${esc(note)}</div>` : "";
  return (
    `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head>` +
    `<body><h1>${title}</h1>${noteHtml}${rows}</body></html>`
  );
}
