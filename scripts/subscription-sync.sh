#!/usr/bin/env bash
set -euo pipefail

# Syncs subscription templates from files to Remnawave Panel API.
# Usage: PANEL_URL=https://... API_TOKEN=... ./sync.sh [dir]

PANEL_URL="${PANEL_URL:?PANEL_URL is required}"
API_TOKEN="${API_TOKEN:?API_TOKEN is required}"
TEMPLATE_DIR="${1:-$(dirname "$0")}"
API="${PANEL_URL}/api/subscription-templates"

# File name → templateType mapping
declare -A TYPE_MAP=(
  [xray-json]=XRAY_JSON
  [singbox]=SINGBOX
  [mihomo]=MIHOMO
  [stash]=STASH
  [clash]=CLASH
)

# Fetch existing templates once
EXISTING=$(curl -sf -H "Authorization: Bearer $API_TOKEN" "$API")

for file in "$TEMPLATE_DIR"/*.json "$TEMPLATE_DIR"/*.yaml "$TEMPLATE_DIR"/*.yml; do
  [ -f "$file" ] || continue

  basename=$(basename "$file")
  name_without_ext="${basename%.*}"
  ext="${basename##*.}"

  # Skip this script's adjacent files that aren't templates
  [ "$name_without_ext" = "sync" ] && continue

  template_type="${TYPE_MAP[$name_without_ext]:-}"
  if [ -z "$template_type" ]; then
    echo "SKIP: $basename (unknown type, expected: ${!TYPE_MAP[*]})"
    continue
  fi

  # Find existing template UUID by type
  uuid=$(echo "$EXISTING" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data['response']['templates']:
    if t['templateType'] == '$template_type':
        print(t['uuid'])
        break
" 2>/dev/null || true)

  if [ -z "$uuid" ]; then
    echo "SKIP: $basename ($template_type not found in Panel, create it in UI first)"
    continue
  fi

  # Build update payload
  if [ "$ext" = "json" ]; then
    payload=$(python3 -c "
import json, sys
with open('$file') as f:
    template = json.load(f)
print(json.dumps({'uuid': '$uuid', 'name': '$name_without_ext', 'templateJson': template}))
")
  else
    encoded=$(base64 -w0 < "$file")
    payload=$(python3 -c "
import json
print(json.dumps({'uuid': '$uuid', 'name': '$name_without_ext', 'encodedTemplateYaml': '$encoded'}))
")
  fi

  response=$(curl -sf -X PATCH \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" \
    "$API" \
    -d "$payload" 2>&1) && echo "OK: $basename → $template_type ($uuid)" \
                        || echo "FAIL: $basename → $response"
done
