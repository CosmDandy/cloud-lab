#!/bin/bash
# Прогон матрицы вариантов Hysteria2 с тестбеда. Каждый вариант: поднять клиент,
# скачать 2 МБ с заблокированного Hetzner через туннель, снять скорость, погасить.
PIN='84:62:5A:04:5A:7B:53:29:B1:49:FF:62:39:F1:A5:56:F2:F1:F4:FF:08:CA:FF:04:D9:B7:A4:5B:2C:2D:8B:22'
TARGET='https://65.108.214.181:8443/blob.bin'
HY=/usr/local/bin/hysteria

run_case() {
  local name="$1" cfg="$2"
  printf '%-34s ' "$name"
  echo "$cfg" > /tmp/c.yaml
  $HY client -c /tmp/c.yaml > /tmp/c.log 2>&1 &
  local pid=$!
  sleep 7
  if ! ss -lntH | awk '{print $4}' | grep -q '127.0.0.1:1081'; then
    echo "НЕ ПОДКЛЮЧИЛСЯ: $(grep -o 'error.*' /tmp/c.log | head -1 | cut -c1-60)"
    kill $pid 2>/dev/null; wait $pid 2>/dev/null; return
  fi
  local r
  r=$(curl -sS -o /dev/null --insecure --max-time 25 --socks5-hostname 127.0.0.1:1081 \
        -w '%{size_download} %{speed_download}' "$TARGET" 2>/dev/null)
  local got=${r%% *} spd=${r##* }
  if [ "$got" = "2097152" ]; then
    printf 'OK   2 МБ, %.1f МБ/с\n' "$(echo "$spd/1048576" | bc -l 2>/dev/null || echo 0)"
  else
    echo "ЧАСТИЧНО получено=$got"
  fi
  kill $pid 2>/dev/null; wait $pid 2>/dev/null
  sleep 2
}

base="auth: testbed-probe-2026
tls:
  insecure: true
  pinSHA256: $PIN
socks5:
  listen: 127.0.0.1:1081"

run_case "1. базовый (parroting вкл)" "server: 85.155.190.66:39443
$base"

run_case "2. parroting выключен" "server: 85.155.190.66:39443
$base
quic:
  disableChromeParrot: true"

run_case "3. brutal (up/down заданы)" "server: 85.155.190.66:39443
$base
bandwidth:
  up: 20 mbps
  down: 100 mbps"

run_case "4. salamander obfs" "server: 85.155.190.66:39444
obfs:
  type: salamander
  salamander:
    password: obfs-probe-2026
$base"

run_case "5. masquerade-сервер" "server: 85.155.190.66:39445
$base"

run_case "6. port hopping 40000-40010" "server: 85.155.190.66:40000-40010
$base"
