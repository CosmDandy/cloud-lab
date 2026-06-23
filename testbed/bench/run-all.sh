#!/usr/bin/env bash
# Main testbed orchestrator. Runs each server-configs/NN-name/ sequentially:
#   1. Start xray-srv container with that config
#   2. Render client config and start xray-cli (SOCKS5 :10808)
#   3. Run bench/benchmark.sh → parse output → render per-variant markdown
#   4. Tear down containers
# After all variants: render SUMMARY.md with comparative table.
#
# Usage:
#   testbed/bench/run-all.sh                     # all variants
#   testbed/bench/run-all.sh 01-vision-base 11   # specific variants by name or index
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

# Load env
if [ -f .env ]; then
    set -a; . .env; set +a
elif [ -f .env.example ]; then
    set -a; . .env.example; set +a
fi

DATE="$(date +%F)"
RESULTS_DIR="results/$DATE"
mkdir -p "$RESULTS_DIR"

XRAY_IMAGE="${XRAY_IMAGE:-ghcr.io/xtls/xray-core:latest}"

cleanup() {
    docker rm -f xray-srv xray-cli >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Variant selection
ALL_DIRS=(server-configs/*/)
SELECTED=()
if [ "$#" -eq 0 ]; then
    SELECTED=("${ALL_DIRS[@]}")
else
    for arg in "$@"; do
        for d in "${ALL_DIRS[@]}"; do
            name="$(basename "$d")"
            if [[ "$name" == "$arg" || "$name" == "${arg}-"* || "${name%%-*}" == "$arg" || "${name%%-*}" == "0$arg" ]]; then
                SELECTED+=("$d")
            fi
        done
    done
fi
[ "${#SELECTED[@]}" -eq 0 ] && { echo "no matching variants"; exit 1; }

echo "==> Testbed run $DATE — ${#SELECTED[@]} variant(s)"
echo

render_md() {
    # Args: <variant-name> <raw-bench-output-file> <output-md>
    local v="$1" raw="$2" md="$3"
    python3 - "$v" "$raw" "$md" <<'PYEOF'
import sys, json, os
variant, raw, md = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
with open(raw) as f:
    for line in f:
        if "=" in line:
            k, v = line.rstrip("\n").split("=", 1)
            data[k] = v

def mbps(b):
    try:
        return f"{int(b) * 8 / 1_000_000:.1f}"
    except Exception:
        return "—"

# Parse handshake_raw "tcp=0.0123 tls=0.0456 ttfb=0.0789 total=0.0900 httpcode=200"
hs = {}
for tok in data.get("handshake_raw", "").split():
    if "=" in tok:
        k, v = tok.split("=", 1)
        hs[k] = v

# Try reading server index for variant meta
meta = {}
try:
    with open("server-configs/index.json") as f:
        meta = json.load(f).get(variant, {})
except Exception:
    pass

with open(md, "w") as f:
    f.write(f"# {variant}\n\n")
    f.write(f"**Run:** {data.get('timestamp', '—')}\n\n")
    f.write("## Config\n\n")
    f.write("| Field | Value |\n|---|---|\n")
    for k in ("port", "network", "sni", "flow", "mode", "path", "service_name", "multi_mode", "sockopt", "xmux", "testpre"):
        if k in meta and meta[k] is not None:
            f.write(f"| {k} | `{meta[k]}` |\n")
    f.write("\n## Handshake\n\n")
    f.write("| Stage | Seconds |\n|---|---|\n")
    f.write(f"| TCP connect | {hs.get('tcp', '—')} |\n")
    f.write(f"| TLS+Reality handshake | {hs.get('tls', '—')} |\n")
    f.write(f"| TTFB | {hs.get('ttfb', '—')} |\n")
    f.write(f"| Total (1 KB) | {hs.get('total', '—')} |\n")
    f.write(f"| HTTP code | {hs.get('httpcode', '—')} |\n\n")

    f.write("## Throughput\n\n")
    f.write("| | bytes/s | Mbit/s |\n|---|---|---|\n")
    f.write(f"| DL avg | {data.get('dl_avg_bytes_s','—')} | {mbps(data.get('dl_avg_bytes_s', 0))} |\n")
    f.write(f"| DL max | {data.get('dl_max_bytes_s','—')} | {mbps(data.get('dl_max_bytes_s', 0))} |\n")
    f.write(f"| UL avg | {data.get('ul_avg_bytes_s','—')} | {mbps(data.get('ul_avg_bytes_s', 0))} |\n")
    f.write(f"| UL max | {data.get('ul_max_bytes_s','—')} | {mbps(data.get('ul_max_bytes_s', 0))} |\n\n")
    f.write(f"DL fails: {data.get('dl_fails','—')} / UL fails: {data.get('ul_fails','—')}\n\n")

    f.write("## Connection-freezing probes\n\n")
    f.write("| Payload | Result |\n|---|---|\n")
    for b in (5000, 16000, 50000):
        f.write(f"| {b//1000} KB | `{data.get(f'freeze_{b}', '—')}` |\n")
    f.write("\n")

    f.write("## Raw\n\n```\n")
    with open(raw) as r:
        f.write(r.read())
    f.write("```\n")
print(f"  → {md}")
PYEOF
}

for D in "${SELECTED[@]}"; do
    NAME="$(basename "$D")"
    PORT="$(jq -r '.inbounds[0].port' "$D/config.json")"
    echo "---"
    echo "[*] $NAME (port $PORT)"

    # 1. Start server
    docker rm -f xray-srv >/dev/null 2>&1 || true
    docker run -d --name xray-srv --network host \
        -v "$ROOT/$D:/etc/xray:ro" \
        "$XRAY_IMAGE" -c /etc/xray/config.json >/dev/null

    # Wait briefly for listen
    for _ in $(seq 1 10); do
        ss -tlnp 2>/dev/null | grep -q ":$PORT " && break
        sleep 0.5
    done
    if ! ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
        echo "  ! server did not start listening on :$PORT — skipping"
        docker logs xray-srv 2>&1 | tail -20
        docker rm -f xray-srv >/dev/null 2>&1
        continue
    fi

    # 2. Render client config
    python3 "$ROOT/render-client.py" "$D" --server-host="${SERVER_HOST:-127.0.0.1}" > /tmp/xray-client.json

    # 3. Start client
    docker rm -f xray-cli >/dev/null 2>&1 || true
    docker run -d --name xray-cli --network host \
        -v /tmp/xray-client.json:/etc/xray/config.json:ro \
        "$XRAY_IMAGE" -c /etc/xray/config.json >/dev/null
    sleep 2

    # 4. Benchmark
    RAW="$RESULTS_DIR/${NAME}.raw"
    MD="$RESULTS_DIR/${NAME}.md"
    if bash "$ROOT/bench/benchmark.sh" "$NAME" > "$RAW" 2>&1; then
        render_md "$NAME" "$RAW" "$MD"
    else
        echo "  ! benchmark failed"
        cat "$RAW" | head -20
    fi

    # 5. Teardown
    docker rm -f xray-srv xray-cli >/dev/null 2>&1 || true
    sleep 1
done

# 6. Summary
echo "---"
python3 - <<'PYEOF' "$RESULTS_DIR"
import sys, json, os, glob
out_dir = sys.argv[1]
rows = []
for f in sorted(glob.glob(f"{out_dir}/*.raw")):
    name = os.path.basename(f)[:-4]
    d = {}
    for line in open(f):
        if "=" in line:
            k, v = line.rstrip().split("=", 1)
            d[k] = v
    hs = {}
    for tok in d.get("handshake_raw", "").split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            hs[k] = v
    def mb(b):
        try: return f"{int(b) * 8 / 1_000_000:.1f}"
        except: return "—"
    rows.append({
        "v": name,
        "tcp": hs.get("tcp", "—"),
        "tls": hs.get("tls", "—"),
        "ttfb": hs.get("ttfb", "—"),
        "dl_mb": mb(d.get("dl_avg_bytes_s", 0)),
        "ul_mb": mb(d.get("ul_avg_bytes_s", 0)),
        "fails": f"{d.get('dl_fails','-')}/{d.get('ul_fails','-')}",
    })

if not rows:
    sys.exit(0)
with open(f"{out_dir}/SUMMARY.md", "w") as f:
    f.write(f"# Testbed summary — {os.path.basename(out_dir)}\n\n")
    f.write("| Variant | TCP s | TLS+Reality s | TTFB s | DL Mbps | UL Mbps | fails dl/ul |\n")
    f.write("|---|---|---|---|---|---|---|\n")
    for r in rows:
        f.write(f"| `{r['v']}` | {r['tcp']} | {r['tls']} | {r['ttfb']} | **{r['dl_mb']}** | **{r['ul_mb']}** | {r['fails']} |\n")
print(f"Summary: {out_dir}/SUMMARY.md")
PYEOF

echo "==> Done. See $RESULTS_DIR/"
