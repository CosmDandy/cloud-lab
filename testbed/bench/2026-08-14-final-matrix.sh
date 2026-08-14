#!/bin/bash
# Полная матрица скоростей в Мбит/с. Один файл 50 МБ, все комбинации.
HY=${HY:-/usr/local/bin/hysteria}
PIN_AMS='84:62:5A:04:5A:7B:53:29:B1:49:FF:62:39:F1:A5:56:F2:F1:F4:FF:08:CA:FF:04:D9:B7:A4:5B:2C:2D:8B:22'
PIN_OSL='B8:1E:AF:F0:E4:BF:4F:80:81:72:35:A4:C8:A7:CC:30:1C:07:AA:58:E1:AD:04:9E:85:09:B2:98:90:23:19:E9'
AMS='https://85.155.190.66:8443/blob50.bin'
HZ='https://65.108.214.181:8443/blob50.bin'
CF='https://speed.cloudflare.com/__down?bytes=26214400'

mbit() { # url [socks]
  local extra="" exp="$3"
  [ -n "$2" ] && extra="--socks5-hostname $2"
  curl -sS -o /dev/null --insecure --max-time 90 $extra \
    -w '%{size_download} %{speed_download}' "$1" 2>/dev/null \
  | awk -v e="$exp" '{ if ($1+0 >= e+0) printf "%6.0f Мбит/с\n", $2*8/1000000; else printf "  ОБРЫВ (%.0f КБ)\n", $1/1024 }'
}

start_hy() { # port pin listen
  printf 'server: %s\nauth: testbed-probe-2026\ntls:\n  insecure: true\n  pinSHA256: %s\nsocks5:\n  listen: 127.0.0.1:%s\n' "$1" "$2" "$3" > /tmp/m.yaml
  $HY client -c /tmp/m.yaml > /tmp/m.log 2>&1 &
  echo $!
}

echo "БЕЗ ТУННЕЛЯ"
printf '  %-32s' '→ Амстердам (50 МБ):';  mbit "$AMS" "" 52428800
printf '  %-32s' '→ Hetzner (50 МБ):';    mbit "$HZ"  "" 52428800
printf '  %-32s' '→ Cloudflare (26 МБ):'; mbit "$CF"  "" 26214400

P=$(start_hy "85.155.190.66:39443" "$PIN_AMS" 1090); sleep 8
echo "ЧЕРЕЗ Hysteria2 → АМСТЕРДАМ (RTT ~47 мс)"
printf '  %-32s' '→ Амстердам (50 МБ):';  mbit "$AMS" 127.0.0.1:1090 52428800
printf '  %-32s' '→ Hetzner (50 МБ):';    mbit "$HZ"  127.0.0.1:1090 52428800
printf '  %-32s' '→ Cloudflare (26 МБ):'; mbit "$CF"  127.0.0.1:1090 26214400
kill $P 2>/dev/null; wait $P 2>/dev/null; sleep 2

P=$(start_hy "91.190.155.237:39443" "$PIN_OSL" 1091); sleep 8
echo "ЧЕРЕЗ Hysteria2 → ОСЛО (RTT ~30 мс)"
printf '  %-32s' '→ Hetzner (50 МБ):';    mbit "$HZ"  127.0.0.1:1091 52428800
printf '  %-32s' '→ Cloudflare (26 МБ):'; mbit "$CF"  127.0.0.1:1091 26214400
kill $P 2>/dev/null; wait $P 2>/dev/null
