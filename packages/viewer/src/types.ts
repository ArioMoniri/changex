// Mirrors the changex-core .changex journal shape (packages/core journal/events.py).
// Kept loose where the core may add fields.

export interface Provenance {
  ts: string;
  session_id: string;
  tool_call_id?: string | null;
  client_name?: string | null;
  client_version?: string | null;
  agent?: string | null;
  vendor?: string | null;
  turn_id?: string | null;
  prompt_sha256?: string | null;
  rationale?: string | null;
  provenance_source: "observed" | "declared";
}

export interface Target {
  node_id: string;
  node_kind: string;
  path: string;
}

export type OpKind =
  | "text.insert"
  | "text.delete"
  | "text.replace"
  | "node.insert"
  | "node.delete"
  | "style.change";

// Op payloads are heterogeneous; index signature keeps the union open.
export interface Op {
  kind: OpKind | string;
  node_id?: string;
  before?: string;
  after?: string;
  text?: string;
  before_anchor?: string | null;
  style?: string;
  node_kind?: string;
  position?: number;
  value?: Record<string, unknown>;
  [extra: string]: unknown;
}

export interface ChangeEvent {
  op_id: string;
  seq: number;
  ts: string;
  provenance: Provenance;
  target: Target;
  op: Op;
  hash: string;
  prev_hash: string | null;
  op_schema_version?: string;
}

export interface JournalHeader {
  changex_version?: string;
  op_schema_version?: string;
  doc?: { filename?: string; baseline_sha256?: string; format?: string; [k: string]: unknown };
  session?: { session_id?: string; capture_mode?: string; [k: string]: unknown };
  node_id_map?: Record<string, string>;
  prev_hash?: null;
  [extra: string]: unknown;
}

export interface Journal {
  header: JournalHeader;
  events: ChangeEvent[];
  path: string;
}

export interface CliResult {
  ok: boolean;
  stdout: string;
  stderr: string;
}
