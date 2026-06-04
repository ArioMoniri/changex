#!/usr/bin/env bash
# Regenerate the README screenshots.
#
# Two steps:
#   1. make_screenshots.py renders a longer, realistic sample per format into the
#      review HTML the app shows by default  ->  docs/assets/_render/<fmt>.html
#   2. headless Chrome snapshots each HTML to a trimmed PNG  ->  docs/assets/<fmt>.png
#
# Requires: the changex packages installed (uv sync / pip install -e ...) and a
# Chromium-family browser on the machine. Safe to re-run; it overwrites the PNGs.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
RENDER="$ROOT/docs/assets/_render"
OUT="$ROOT/docs/assets"

# --- locate a headless-capable browser -------------------------------------- #
CHROME=""
for c in \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  "/Applications/Chromium.app/Contents/MacOS/Chromium" \
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
  "$(command -v google-chrome || true)" \
  "$(command -v chromium || true)" \
  "$(command -v chromium-browser || true)"; do
  if [ -n "$c" ] && [ -x "$c" ]; then CHROME="$c"; break; fi
done

# --- step 1: build the review HTML ------------------------------------------ #
echo "==> rendering review HTML (make_screenshots.py)"
python3 "$HERE/make_screenshots.py"

if [ -z "$CHROME" ]; then
  echo "!! No Chrome/Chromium/Edge found — HTML is in $RENDER but PNGs were not regenerated."
  echo "   Install a Chromium-family browser, or open the .html files and screenshot them by hand."
  exit 0
fi
echo "==> using browser: $CHROME"

# --- step 2: snapshot each HTML to a PNG ------------------------------------ #
# Per-format window widths — docx/xlsx/pptx are wider review surfaces; md/csv are narrow.
snap() {
  local name="$1" width="$2" height="$3"
  local html="$RENDER/$name.html" png="$OUT/$name.png"
  [ -f "$html" ] || { echo "   (skip $name — no $html)"; return; }
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
    --screenshot="$png" --window-size="$width,$height" "file://$html" >/dev/null 2>&1 || true
  echo "   $name -> $png"
}

echo "==> snapshotting PNGs"
snap docx 940 1180
snap md   720 560
snap csv  720 520
snap xlsx 860 620
snap pptx 860 560

echo "==> done. Updated PNGs in $OUT"
