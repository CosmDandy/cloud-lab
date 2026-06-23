#!/usr/bin/env bash
# Remote-server testbed orchestrator.
# Assumes the testbed server bundle is ALREADY running on $SERVER_HOST
# (foreign node, e.g. London) exposing inbounds on ports 11001-11012.
# Runs the Xray CLIENT locally (in RU, on the LXC) → tunnels to the foreign
# server → benchmarks through speed.cloudflare.com (foreign exit = no TSPU throttle).
#
# This is the CORRECT topology: only a foreign exit can be benchmarked, because
# a RU-exit gets throttled on the server→destination leg regardless of protocol.
#
# Usage:
#   SERVER_HOST=194.180.158.12 testbed/bench/run-remote.sh [variant ...]
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

# Prefer .env; fall back to .env.example only if .env is absent.
# Command-line env (e.g. SERVER_HOST=...) wins over file defaults.
if [ -f .env ]; then set -a; . .env; set +a
elif [ -f .env.example ]; then set -a; . .env.example; set +a
fi

: "${SERVER_HOST:?SERVER_HOST required (foreign node IP)}"
XRAY_IMAGE="${XRAY_IMAGE:-ghcr.io/xtls/xray-core:latest}"
DL_BYTES="${DOWNLOAD_BYTES:-50000000}"
REPEATS="${REPEATS:-3}"

DATE="$(date +%F)"
RESULTS_DIR="results/$DATE-london"
mkdir -p "$RESULTS_DIR"

cleanup() { docker rm -f tb-cli >/dev/null 2>&1 || true; }
trap cleanup EXIT

ALL_DIRS=(server-configs/*/)
SELECTED=()
if [ "$#" -eq 0 ]; then SELECTED=("${ALL_DIRS[@]}"); else
  for arg in "$@"; do for d in "${ALL_DIRS[@]}"; do
    n="$(basename "$d")"
    [[ "$n" == "$arg" || "${n%%-*}" == "$arg" || "${n%%-*}" == "0$arg" ]] && SELECTED+=("$d")
  done; done
fi

echo "==> Remote testbed run $DATE — server=$SERVER_HOST — ${#SELECTED[@]} variant(s)"

# Baseline (direct, no VPN) — shows the throttle
DIRECT=$(curl -sS -o /dev/null --max-time 20 -w "%{speed_download}|%{size_download}" \
  "https://speed.cloudflare.com/__down?bytes=$DL_BYTES" 2>/dev/null)
IFS='|' read -r dsp dsz <<< "$DIRECT"
DIRECT_MB=$(python3 -c "print(f'{${dsp:-0}*8/1e6:.1f}')" 2>/dev/null || echo "0")
echo "    baseline direct (no VPN): ${DIRECT_MB} Mbit/s (${dsz:-0} bytes)"
echo

dl_once() {
  curl -sS --proxy socks5h://127.0.0.1:10808 -o /dev/null --max-time 30 \
    -w "%{speed_download}|%{size_download}|%{time_total}" \
    "https://speed.cloudflare.com/__down?bytes=$DL_BYTES" 2>/dev/null
}

for D in "${SELECTED[@]}"; do
  NAME="$(basename "$D")"
  PORT="$(jq -r '.inbounds[0].port' "$D/config.json")"
  echo "[*] $NAME (london:$PORT)"

  python3 "$ROOT/render-client.py" "$D" --server-host="$SERVER_HOST" > /tmp/tb-cli.json 2>/tmp/tb-cli.err
  if [ ! -s /tmp/tb-cli.json ]; then echo "  ! render failed: $(cat /tmp/tb-cli.err)"; continue; fi

  docker rm -f tb-cli >/dev/null 2>&1
  docker run -d --name tb-cli --network host -v /tmp/tb-cli.json:/etc/xray/config.json:ro "$XRAY_IMAGE" -c /etc/xray/config.json >/dev/null
  sleep 3

  EXIT_IP=$(curl -sS --proxy socks5h://127.0.0.1:10808 --max-time 10 "https://speed.cloudflare.com/cdn-cgi/trace" 2>/dev/null | grep -E "^ip=" | head -1 | cut -d= -f2)

  RAW="$RESULTS_DIR/${NAME}.raw"
  { echo "variant=$NAME"; echo "timestamp=$(date -Iseconds)"; echo "server=$SERVER_HOST:$PORT"; echo "exit_ip=${EXIT_IP:-CONNECT-FAIL}"; } > "$RAW"

  HS=$(curl -sS --proxy socks5h://127.0.0.1:10808 -o /dev/null --max-time 15 \
    -w "tcp=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} code=%{http_code}" \
    "https://speed.cloudflare.com/__down?bytes=1024" 2>/dev/null)
  echo "handshake=$HS" >> "$RAW"

  DLSUM=0; DLN=0; DLMAX=0
  for i in $(seq 1 "$REPEATS"); do
    r=$(dl_once); IFS='|' read -r sp _ _ <<< "$r"
    spi=$(printf "%.0f" "${sp:-0}" 2>/dev/null || echo 0)
    echo "dl_run_$i=$spi" >> "$RAW"
    if [ "$spi" -gt 0 ]; then DLSUM=$((DLSUM+spi)); DLN=$((DLN+1)); [ "$spi" -gt "$DLMAX" ] && DLMAX=$spi; fi
  done
  [ "$DLN" -gt 0 ] && echo "dl_avg=$((DLSUM/DLN))" >> "$RAW" || echo "dl_avg=0" >> "$RAW"
  echo "dl_max=$DLMAX" >> "$RAW"

  AVG_MB=$(python3 -c "print(f'{$((DLN>0?DLSUM/DLN:0))*8/1e6:.1f}')" 2>/dev/null)
  echo "  exit=${EXIT_IP:-FAIL}  DL avg=${AVG_MB} Mbit/s  ($HS)"
  docker rm -f tb-cli >/dev/null 2>&1
  sleep 1
done

# Summary
python3 - "$RESULTS_DIR" "$DIRECT_MB" <<'PY'
import sys, glob, os
rd, direct = sys.argv[1], sys.argv[2]
rows=[]
for f in sorted(glob.glob(f"{rd}/*.raw")):
    d={}
    for line in open(f):
        if "=" in line: k,v=line.rstrip().split("=",1); d[k]=v
    hs={}
    for tok in d.get("handshake","").split():
        if "=" in tok: k,v=tok.split("=",1); hs[k]=v
    mb=lambda b: f"{int(b)*8/1e6:.1f}" if b and b.isdigit() else "—"
    rows.append((os.path.basename(f)[:-4], hs.get("tcp","—"), hs.get("tls","—"),
                 hs.get("ttfb","—"), mb(d.get("dl_avg","0")), mb(d.get("dl_max","0")), d.get("exit_ip","—")))
with open(f"{rd}/SUMMARY.md","w") as o:
    o.write(f"# Testbed (London exit) — {os.path.basename(rd)}\n\n")
    o.write(f"**Baseline direct (no VPN):** {direct} Mbit/s — throttled by TSPU\n\n")
    o.write("| Variant | TCP s | TLS+Reality s | TTFB s | DL avg Mbit/s | DL max Mbit/s | exit |\n")
    o.write("|---|---|---|---|---|---|---|\n")
    for r in sorted(rows, key=lambda x: -(float(x[4]) if x[4]!="—" else 0)):
        o.write(f"| `{r[0]}` | {r[1]} | {r[2]} | {r[3]} | **{r[4]}** | {r[5]} | {r[6]} |\n")
print(f"\nSummary: {rd}/SUMMARY.md")
PY
echo "==> Done. $RESULTS_DIR/"
