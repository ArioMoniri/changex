#!/usr/bin/env bash
#
# ChangeX 60-second demo — the active/CLI path, end to end.
#
# Runs the M0 spine against examples/sample.docx and shows you exactly where
# every artifact landed:
#
#   1. track   — apply two semantic edits, emit a tracked .docx (native Word
#                revisions) + a .changex provenance journal
#   2. review  — render a single-file HTML redline you can open or share
#   3. verify  — re-hash the baseline + walk the hash chain
#
# It prints the path to each output and a one-liner to open the report and to
# launch the interactive local webserver (changex view).
#
# Usage:   ./scripts/demo.sh            # from the repo root
#          make demo                    # same thing
#
# Requires the `changex` CLI on PATH. Get it with:  uv sync  (or  make install).

set -euo pipefail

# --------------------------------------------------------------------------- #
# Locate the repo root (this script lives in scripts/) and the CLI.
# Prefer a workspace .venv if present, else fall back to `changex` on PATH.
# --------------------------------------------------------------------------- #
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -x "${ROOT}/.venv/bin/changex" ]]; then
  CHANGEX="${ROOT}/.venv/bin/changex"
elif command -v changex >/dev/null 2>&1; then
  CHANGEX="$(command -v changex)"
else
  echo "error: 'changex' CLI not found." >&2
  echo "       Install it first:  uv sync   (or  make install,  or  pip install changex)" >&2
  exit 1
fi

SAMPLE="${ROOT}/examples/sample.docx"
if [[ ! -f "${SAMPLE}" ]]; then
  echo "error: sample document missing: ${SAMPLE}" >&2
  echo "       Generate it with:  python scripts/make_sample_docx.py" >&2
  exit 1
fi

# All artifacts land in examples/out/ (gitignored).
OUT="${ROOT}/examples/out"
mkdir -p "${OUT}"
TRACKED="${OUT}/demo-tracked.docx"
JOURNAL="${OUT}/demo-session.changex"
REPORT="${OUT}/demo-review.html"
OPS="${OUT}/demo-ops.json"

# Start clean so the demo is reproducible (the journal is append-only).
rm -f "${TRACKED}" "${JOURNAL}" "${REPORT}" "${OPS}"

# --------------------------------------------------------------------------- #
# Discover the body paragraph's node_id so the demo is robust to fixture edits
# (paragraph ids reuse Word's native w14:paraId; we don't hard-code them).
# --------------------------------------------------------------------------- #
BODY_ID="$(
  "${ROOT}/.venv/bin/python" - "${SAMPLE}" 2>/dev/null <<'PY' || \
  python3 - "${SAMPLE}" <<'PY'
import sys
import changex_core as cx
adapter = cx.DocxAdapter.load(sys.argv[1], author="changex-demo")
# The "quick brown fox" sentence is paragraph index 1 in the sample fixture.
print(adapter.to_model().child_paragraphs()[1].node_id)
PY
)"

if [[ -z "${BODY_ID}" ]]; then
  echo "error: could not resolve the sample's body paragraph node_id." >&2
  echo "       Is changex-core importable?  Try:  uv sync" >&2
  exit 1
fi

# Two narrowly-typed text edits to that paragraph (the journal records each with
# split observed/declared provenance, authored by the model id we pass below).
cat > "${OPS}" <<JSON
[
  {"kind": "text.replace", "node_id": "${BODY_ID}", "before": "quick", "after": "swift",
   "rationale": "tighten wording: quick -> swift"},
  {"kind": "text.replace", "node_id": "${BODY_ID}", "before": "lazy", "after": "sleepy",
   "rationale": "soften tone: lazy -> sleepy"}
]
JSON

echo "==> ChangeX demo  (sample: ${SAMPLE})"
echo

echo "[1/3] track  — apply 2 edits, emit tracked .docx + .changex journal"
"${CHANGEX}" track "${SAMPLE}" "${OPS}" \
  --out "${TRACKED}" \
  --changex "${JOURNAL}" \
  --author "claude-opus-4-8"
echo

echo "[2/3] review — render a single-file HTML redline"
"${CHANGEX}" review "${JOURNAL}" --out "${REPORT}"
echo

echo "[3/3] verify — re-hash baseline + walk the hash chain"
"${CHANGEX}" verify "${JOURNAL}" --baseline "${SAMPLE}"
echo

# --------------------------------------------------------------------------- #
# Summary: where everything landed + how to see it.
# --------------------------------------------------------------------------- #
echo "Done. Outputs in ${OUT}:"
echo "  tracked docx (native Word revisions) : ${TRACKED}"
echo "  provenance journal (.changex)        : ${JOURNAL}"
echo "  single-file HTML report              : ${REPORT}"
echo
echo "See it:"
echo "  open report   ->  open '${REPORT}'        # or just double-click it"
echo "  open in Word  ->  open '${TRACKED}'        # real accept/reject revisions"
echo "  interactive   ->  ${CHANGEX} view '${JOURNAL}' --doc '${TRACKED}'"
