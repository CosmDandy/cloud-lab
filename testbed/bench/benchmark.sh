#!/usr/bin/env bash
# Single-variant benchmark through xray-cli's SOCKS5 (default localhost:10808).
# Output: machine-readable lines `KEY=value`. The run-all.sh wrapper parses and aggregates.
#
# Usage:
#   benchmark.sh <variant-name>
set -euo pipefail

VARIANT="${1:?variant name required}"
PROXY="${PROXY:-socks5h://127.0.0.1:10808}"
URL="${URL:-https://speed.cloudflare.com}"
DL_BYTES="${DOWNLOAD_BYTES:-200000000}"
UL_BYTES="${UPLOAD_BYTES:-50000000}"
REPEATS="${REPEATS:-3}"

# Curl baseline opts
C="curl -sS --proxy $PROXY --max-time 120"

# Pre-warm Reality handshake (TLS-in-TLS not measured for first hit)
$C -o /dev/null "$URL/cdn-cgi/trace" >/dev/null 2>&1 || true
sleep 1

emit() { printf '%s=%s\n' "$1" "$2"; }

emit variant "$VARIANT"
emit timestamp "$(date -Iseconds)"

# 1. Handshake metrics (single small request)
HS=$($C -o /dev/null -w "tcp=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total} httpcode=%{http_code}" \
     "$URL/__down?bytes=1024" 2>&1) || HS="error=connect-fail"
emit "handshake_raw" "$HS"

# 2. Download throughput
DL_TOTAL=0
DL_MAX=0
DL_FAILS=0
for i in $(seq 1 "$REPEATS"); do
    SPEED=$($C -o /dev/null -w "%{speed_download}" "$URL/__down?bytes=$DL_BYTES" 2>/dev/null) || { DL_FAILS=$((DL_FAILS+1)); continue; }
    SPEED_INT=$(printf "%.0f" "$SPEED")
    emit "dl_run_$i" "$SPEED_INT"
    DL_TOTAL=$((DL_TOTAL + SPEED_INT))
    [ "$SPEED_INT" -gt "$DL_MAX" ] && DL_MAX=$SPEED_INT
done
GOOD_DL=$((REPEATS - DL_FAILS))
if [ "$GOOD_DL" -gt 0 ]; then
    emit "dl_avg_bytes_s" "$((DL_TOTAL / GOOD_DL))"
    emit "dl_max_bytes_s" "$DL_MAX"
fi
emit "dl_fails" "$DL_FAILS"

# 3. Upload throughput (random bytes from /dev/urandom)
UL_TOTAL=0
UL_MAX=0
UL_FAILS=0
TMPFILE=$(mktemp)
head -c "$UL_BYTES" /dev/urandom > "$TMPFILE"
for i in $(seq 1 "$REPEATS"); do
    SPEED=$($C -X POST --data-binary "@$TMPFILE" -o /dev/null -w "%{speed_upload}" "$URL/__up" 2>/dev/null) || { UL_FAILS=$((UL_FAILS+1)); continue; }
    SPEED_INT=$(printf "%.0f" "$SPEED")
    emit "ul_run_$i" "$SPEED_INT"
    UL_TOTAL=$((UL_TOTAL + SPEED_INT))
    [ "$SPEED_INT" -gt "$UL_MAX" ] && UL_MAX=$SPEED_INT
done
rm -f "$TMPFILE"
GOOD_UL=$((REPEATS - UL_FAILS))
if [ "$GOOD_UL" -gt 0 ]; then
    emit "ul_avg_bytes_s" "$((UL_TOTAL / GOOD_UL))"
    emit "ul_max_bytes_s" "$UL_MAX"
fi
emit "ul_fails" "$UL_FAILS"

# 4. Connectivity / target metadata
META=$($C "$URL/meta" 2>/dev/null) || META="{}"
emit "cf_meta" "$(echo "$META" | tr '\n' ' ')"

# 5. Connection freezing probe — small payloads at 5/16/50 KB
for BYTES in 5000 16000 50000; do
    OK="ok"
    $C -o /dev/null --max-time 10 "$URL/__down?bytes=$BYTES" >/dev/null 2>&1 || OK="fail"
    emit "freeze_${BYTES}" "$OK"
done
