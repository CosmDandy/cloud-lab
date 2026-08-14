#!/bin/bash
# Синхронный ряд: каждую минуту — 4 параллельных к Cloudflare, 3 последовательных к CF,
# и контроль к своей ноде. Метки времени UTC для сопоставления между машинами.
LOG=/tmp/paired.log
CF="https://speed.cloudflare.com/__down?bytes=100000"
OWN="https://167.104.104.131:8443/blob.bin"
: > "$LOG"
for round in $(seq 1 14); do
  TS=$(date -u +%H:%M:%SZ)
  # 4 параллельных к Cloudflare
  for i in 1 2 3 4; do
    curl -sS -o /dev/null --max-time 7 -w '%{size_download}\n' "$CF" 2>/dev/null &
  done > /tmp/par.tmp
  wait
  par=$(grep -c '^100000$' /tmp/par.tmp 2>/dev/null || echo 0)
  # 3 последовательных к Cloudflare
  seq_ok=0
  for i in 1 2 3; do
    sz=$(curl -sS -o /dev/null --max-time 7 -w '%{size_download}' "$CF" 2>/dev/null)
    [ "$sz" = "100000" ] && seq_ok=$((seq_ok+1))
  done
  # контроль: своя нода, 2 МБ
  own=$(curl -sS -o /dev/null --insecure --max-time 15 -w '%{size_download}' "$OWN" 2>/dev/null)
  echo "$TS par4=$par/4 seq=$seq_ok/3 own=$own" >> "$LOG"
  rm -f /tmp/par.tmp
  sleep 45
done
echo "конец" >> "$LOG"
