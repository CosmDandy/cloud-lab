#!/bin/bash
U='https://speed.cloudflare.com/__down?bytes=26214400'
m() { curl -sS -o /dev/null --max-time 60 --socks5-hostname 127.0.0.1:1100 -w '%{size_download} %{speed_download}' "$U" 2>/dev/null \
      | awk '{ if ($1==26214400) printf "%.0f Мбит/с\n", $2*8/1000000; else printf "не докачал (%.0f КБ)\n", $1/1024 }'; }
x() { printf '  %-40s ' "$1"; pkill -f "bench.json" 2>/dev/null; sleep 1
      cat > /tmp/bench.json <<JSON
{"log":{"loglevel":"warning"},
 "inbounds":[{"port":1100,"listen":"127.0.0.1","protocol":"socks","settings":{"udp":true}}],
 "outbounds":[{"protocol":"hysteria",
  "settings":{"version":2,"address":"hhh-sto-01.vpn.cosmdandy.dev","port":$2},
  "streamSettings":{"network":"hysteria","security":"tls",
    "tlsSettings":{"alpn":["h3"],"serverName":"hhh-sto-01.vpn.cosmdandy.dev"},
    "hysteriaSettings":{"version":2,"auth":"bench-2026"}$3}}]}
JSON
      nohup /usr/local/bin/xray run -c /tmp/bench.json > /tmp/bench.log 2>&1 &
      sleep 7; m; pkill -f "bench.json" 2>/dev/null; sleep 1; }
x "Xray-инбаунд, БЕЗ обфускации" 39601 ""
x "Xray-инбаунд, finalMask.salamander" 39602 ',"finalMask":{"salamander":{"password":"ЗАМЕНИТЬ"}}'
printf '  %-40s ' "apernet-демон, salamander (для сравнения)"
printf 'server: hhh-sto-01.vpn.cosmdandy.dev:47821\nauth: ЗАМЕНИТЬ\nobfs:\n  type: salamander\n  salamander:\n    password: ЗАМЕНИТЬ\nsocks5:\n  listen: 127.0.0.1:1100\n' > /tmp/ap.yaml
pkill -f "ap.yaml" 2>/dev/null; sleep 1
nohup /usr/local/bin/hysteria client -c /tmp/ap.yaml > /tmp/ap.log 2>&1 &
sleep 7; m; pkill -f "ap.yaml" 2>/dev/null
