#!/usr/bin/env bash
set -euo pipefail

# Syncs Panel config (config profiles, nodes, hosts) from config.json to Remnawave API.
# Idempotent: skips entities that already exist (matched by name/remark).
# Usage: PANEL_URL=https://... API_TOKEN=... ./sync.sh [config.json]

PANEL_URL="${PANEL_URL:?PANEL_URL is required}"
API_TOKEN="${API_TOKEN:?API_TOKEN is required}"
CONFIG_FILE="${1:-$(dirname "$0")/config.json}"
API="${PANEL_URL}/api"

AUTH=("Authorization: Bearer $API_TOKEN")

api_get()  { curl -sf -H "${AUTH[0]}" "$API/$1"; }
api_post() { curl -sf -X POST -H "${AUTH[0]}" -H "Content-Type: application/json" "$API/$1" -d "$2"; }

CONFIG=$(cat "$CONFIG_FILE")

# ── 1. Config Profiles ──────────────────────────────────────────────────────

echo "=== Config Profiles ==="
EXISTING_PROFILES=$(api_get "config-profiles")

PROFILE_COUNT=$(echo "$CONFIG" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['configProfiles']))")

for i in $(seq 0 $((PROFILE_COUNT - 1))); do
  PROFILE_NAME=$(echo "$CONFIG" | python3 -c "import sys,json; print(json.load(sys.stdin)['configProfiles'][$i]['name'])")
  PROFILE_CONFIG=$(echo "$CONFIG" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['configProfiles'][$i]['config']))")

  # Check if profile exists
  EXISTING_UUID=$(echo "$EXISTING_PROFILES" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for p in data['response']['configProfiles']:
    if p['name'] == '$PROFILE_NAME':
        print(p['uuid'])
        break
" 2>/dev/null || true)

  if [ -n "$EXISTING_UUID" ]; then
    echo "  SKIP: $PROFILE_NAME (exists: $EXISTING_UUID)"
  else
    RESULT=$(api_post "config-profiles" "{\"name\": \"$PROFILE_NAME\", \"config\": $PROFILE_CONFIG}")
    UUID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['response']['uuid'])")
    echo "  OK: $PROFILE_NAME → $UUID"
  fi
done

# Refresh profiles to get UUIDs and inbound UUIDs
EXISTING_PROFILES=$(api_get "config-profiles")

# ── 2. Nodes ────────────────────────────────────────────────────────────────

echo "=== Nodes ==="
EXISTING_NODES=$(api_get "nodes")

NODE_COUNT=$(echo "$CONFIG" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['nodes']))")

for i in $(seq 0 $((NODE_COUNT - 1))); do
  NODE=$(echo "$CONFIG" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['nodes'][$i]))")
  NODE_NAME=$(echo "$NODE" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])")

  EXISTING_UUID=$(echo "$EXISTING_NODES" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for n in data['response']:
    if n['name'] == '$NODE_NAME':
        print(n['uuid'])
        break
" 2>/dev/null || true)

  if [ -n "$EXISTING_UUID" ]; then
    echo "  SKIP: $NODE_NAME (exists: $EXISTING_UUID)"
    continue
  fi

  # Resolve config profile name → UUID + inbound UUIDs
  PAYLOAD=$(python3 -c "
import json, sys

node = json.loads('''$NODE''')
profiles = json.loads('''$(echo "$EXISTING_PROFILES" | tr "'" '"')''')

profile_name = node.pop('configProfile')
profile = None
for p in profiles['response']['configProfiles']:
    if p['name'] == profile_name:
        profile = p
        break

if not profile:
    print(f'ERROR: Config profile {profile_name} not found', file=sys.stderr)
    sys.exit(1)

inbound_uuids = [ib['uuid'] for ib in profile['inbounds']]

node['configProfile'] = {
    'activeConfigProfileUuid': profile['uuid'],
    'activeInbounds': inbound_uuids
}
node['isTrafficTrackingActive'] = True

print(json.dumps(node))
")

  RESULT=$(api_post "nodes" "$PAYLOAD")
  UUID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['response']['uuid'])")
  echo "  OK: $NODE_NAME → $UUID"
done

# Refresh nodes
EXISTING_NODES=$(api_get "nodes")

# ── 3. Hosts ────────────────────────────────────────────────────────────────

echo "=== Hosts ==="
EXISTING_HOSTS=$(api_get "hosts")

HOST_COUNT=$(echo "$CONFIG" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['hosts']))")

for i in $(seq 0 $((HOST_COUNT - 1))); do
  HOST=$(echo "$CONFIG" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['hosts'][$i]))")
  HOST_REMARK=$(echo "$HOST" | python3 -c "import sys,json; print(json.load(sys.stdin)['remark'])")

  EXISTING_UUID=$(echo "$EXISTING_HOSTS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for h in data['response']:
    if h['remark'] == '$HOST_REMARK':
        print(h['uuid'])
        break
" 2>/dev/null || true)

  if [ -n "$EXISTING_UUID" ]; then
    echo "  SKIP: $HOST_REMARK (exists: $EXISTING_UUID)"
    continue
  fi

  PAYLOAD=$(python3 -c "
import json, sys

host = json.loads('''$HOST''')
profiles = json.loads('''$(echo "$EXISTING_PROFILES" | tr "'" '"')''')
nodes = json.loads('''$(echo "$EXISTING_NODES" | tr "'" '"')''')

# Resolve config profile + inbound tag → UUIDs
profile_name = host.pop('configProfile')
inbound_tag = host.pop('inboundTag')
node_names = host.pop('nodes')

profile = None
for p in profiles['response']['configProfiles']:
    if p['name'] == profile_name:
        profile = p
        break

inbound_uuid = None
for ib in profile['inbounds']:
    if ib['tag'] == inbound_tag:
        inbound_uuid = ib['uuid']
        break

host['inbound'] = {
    'configProfileUuid': profile['uuid'],
    'configProfileInboundUuid': inbound_uuid
}

# Resolve node names → UUIDs
host['nodes'] = []
for nn in node_names:
    for n in nodes['response']:
        if n['name'] == nn:
            host['nodes'].append(n['uuid'])
            break

print(json.dumps(host))
")

  RESULT=$(api_post "hosts" "$PAYLOAD")
  UUID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['response']['uuid'])")
  echo "  OK: $HOST_REMARK → $UUID"
done

echo "=== Done ==="
