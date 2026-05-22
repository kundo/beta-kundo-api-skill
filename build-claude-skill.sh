#!/bin/bash
# Build a Claude.ai skill bundle (zip) from the plugin sources.
#
# Output: dist/kundo-api.zip
#   SKILL.md          (paths rewritten: no ${CLAUDE_PLUGIN_ROOT})
#   REFERENCE.md
#   scripts/kapi.py
#
# Upload that zip in claude.ai → Settings → Capabilities → Skills.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/skills/kundo-api"
DIST="$ROOT/dist"
STAGE="$DIST/stage"

rm -rf "$STAGE" "$DIST/kundo-api.zip"
mkdir -p "$STAGE/scripts"

cp "$SRC/REFERENCE.md"        "$STAGE/REFERENCE.md"
cp "$SRC/scripts/kapi.py"     "$STAGE/scripts/kapi.py"
chmod +x "$STAGE/scripts/kapi.py"

# Flatten plugin paths for the claude.ai bundle layout:
#   ${CLAUDE_PLUGIN_ROOT}/skills/kundo-api/scripts/kapi.py  -->  scripts/kapi.py
sed 's|"\${CLAUDE_PLUGIN_ROOT}/skills/kundo-api/|"|g; s|\${CLAUDE_PLUGIN_ROOT}/skills/kundo-api/||g' \
  "$SRC/SKILL.md" > "$STAGE/SKILL.md"

cd "$STAGE"
zip -qr "$DIST/kundo-api.zip" .
cd "$ROOT"

echo "Built: $DIST/kundo-api.zip"
unzip -l "$DIST/kundo-api.zip"
