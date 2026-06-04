#!/usr/bin/env bash
# Build the ChangeX Quick Look app (host app + embedded .changex preview extension).
#
#   ./build.sh            # unsigned build (local testing)  -> build/Release/ChangeXQuickLook.app
#   SIGN_ID="Developer ID Application: NAME (TEAMID)" ./build.sh   # signed
#
# Requires: Xcode + xcodegen (brew install xcodegen).
set -euo pipefail
cd "$(dirname "$0")"

command -v xcodegen >/dev/null || { echo "needs xcodegen: brew install xcodegen"; exit 1; }
xcodegen generate

ARGS=(-project ChangeXQuickLook.xcodeproj -scheme ChangeXQuickLook -configuration Release SYMROOT=build)
if [ -n "${SIGN_ID:-}" ]; then
  xcodebuild "${ARGS[@]}" CODE_SIGN_IDENTITY="$SIGN_ID" build
else
  xcodebuild "${ARGS[@]}" CODE_SIGNING_ALLOWED=NO build
fi
echo "✓ built: $(pwd)/build/Release/ChangeXQuickLook.app"
