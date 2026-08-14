#!/bin/bash
HY=${HY:-/usr/local/bin/hysteria}
U='https://speed.cloudflare.com/__down?bytes=26214400'
m() { curl -sS -o /dev/null --max-time 60 $2 -w '%{size_download} %{speed_download}' "$1" 2>/dev/null \
      | awk '{ if ($1==26214400) printf "%.0f Мбит/с  ", $2*8/1000000; else printf "ОБРЫВ(%.0fКБ)  ", $1/1024 }'; }
printf '  напрямую:        '; for i in 1 2 3; do m "$U"; done; echo
printf 'server: 85.155.190.66:39443\nauth: testbed-probe-2026\ntls:\n  insecure: true\n  pinSHA256: %s\nsocks5:\n  listen: 127.0.0.1:1088\n' '84:62:5A:04:5A:7B:53:29:B1:49:FF:62:39:F1:A5:56:F2:F1:F4:FF:08:CA:FF:04:D9:B7:A4:5B:2C:2D:8B:22' > /tmp/cf2.yaml
$HY client -c /tmp/cf2.yaml > /tmp/cf2.log 2>&1 &
P=$!
sleep 8
printf '  через Hysteria2: '; for i in 1 2 3; do m "$U" "--socks5-hostname 127.0.0.1:1088"; done; echo
kill $P 2>/dev/null
