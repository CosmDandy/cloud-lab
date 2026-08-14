#!/bin/bash
# Полная матрица: две цели (чистая/заблокированная) × прямо и через туннель.
PIN='84:62:5A:04:5A:7B:53:29:B1:49:FF:62:39:F1:A5:56:F2:F1:F4:FF:08:CA:FF:04:D9:B7:A4:5B:2C:2D:8B:22'
AMS='https://85.155.190.66:8443/blob.bin'
HZ='https://65.108.214.181:8443/blob.bin'
HY=${HY:-/usr/local/bin/hysteria}

meas() { # url [socks]
  local extra=""
  [ -n "$2" ] && extra="--socks5-hostname $2"
  curl -sS -o /dev/null --insecure --max-time 40 $extra \
    -w '%{size_download} %{speed_download}' "$1" 2>/dev/null \
  | awk '{ if ($1==2097152) printf "%.2f МБ/с\n", $2/1048576; else printf "ОБРЫВ на %s байт\n", $1 }'
}

echo "=== НАПРЯМУЮ (без туннеля) ==="
printf '  %-40s ' "→ Амстердам (чистая цель), TCP/TLS:"; meas "$AMS"
printf '  %-40s ' "→ Hetzner (заблокирован), TCP/TLS:";  meas "$HZ"

printf 'server: 85.155.190.66:39443\nauth: testbed-probe-2026\ntls:\n  insecure: true\n  pinSHA256: %s\nsocks5:\n  listen: 127.0.0.1:1085\n' "$PIN" > /tmp/full.yaml
$HY client -c /tmp/full.yaml > /tmp/full.log 2>&1 &
PID=$!
sleep 10
echo "=== ЧЕРЕЗ Hysteria2 (туннель на Амстердам) ==="
printf '  %-40s ' "→ Амстердам:"; meas "$AMS" 127.0.0.1:1085
printf '  %-40s ' "→ Hetzner:";   meas "$HZ"  127.0.0.1:1085
kill $PID 2>/dev/null; wait $PID 2>/dev/null
