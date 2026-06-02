import type { ChangeEvent } from "../types";

const KIND_LABEL: Record<string, string> = {
  "text.insert": "Insert text",
  "text.delete": "Delete text",
  "text.replace": "Replace text",
  "node.insert": "Insert paragraph",
  "node.delete": "Delete paragraph",
  "style.change": "Change style",
};

function changeSummary(ev: ChangeEvent): string {
  const op = ev.op;
  switch (op.kind) {
    case "text.insert":
      return `+ "${op.text ?? ""}"`;
    case "text.delete":
      return `- "${op.before ?? ""}"`;
    case "text.replace":
      return `"${op.before ?? ""}" -> "${op.after ?? ""}"`;
    case "style.change":
      return `${op.before ?? "?"} -> ${op.style ?? "?"}`;
    case "node.insert":
      return `+ "${(op.value as { text?: string })?.text ?? ""}"`;
    case "node.delete":
      return `- "${(op.value as { text?: string })?.text ?? ""}"`;
    default:
      return String(op.kind);
  }
}

interface Props {
  events: ChangeEvent[];
  selectedSeq: number | null;
  onSelect: (seq: number) => void;
}

/** Vertical provenance timeline: one entry per journal event. */
export function ProvenanceTimeline({ events, selectedSeq, onSelect }: Props) {
  if (events.length === 0) {
    return <p className="empty">No events in this journal.</p>;
  }
  return (
    <ol className="timeline">
      {events.map((ev) => {
        const p = ev.provenance;
        const who = p.agent ?? p.client_name ?? "unknown";
        const selected = ev.seq === selectedSeq;
        return (
          <li
            key={ev.op_id}
            className={`tl-item${selected ? " selected" : ""}`}
            onClick={() => onSelect(ev.seq)}
          >
            <div className="tl-dot" aria-hidden />
            <div className="tl-body">
              <div className="tl-head">
                <span className="tl-seq">#{ev.seq}</span>
                <span className="tl-kind">{KIND_LABEL[ev.op.kind] ?? ev.op.kind}</span>
                <span className={`tl-src tl-src-${p.provenance_source}`}>
                  {p.provenance_source}
                </span>
              </div>
              <code className="tl-change">{changeSummary(ev)}</code>
              <div className="tl-meta">
                <span title="target node">{ev.target.node_id}</span>
                <span title="author">{who}</span>
                {p.vendor ? <span title="vendor">{p.vendor}</span> : null}
                <span title="timestamp">{p.ts}</span>
              </div>
              {p.rationale ? <div className="tl-rationale">&ldquo;{p.rationale}&rdquo;</div> : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
