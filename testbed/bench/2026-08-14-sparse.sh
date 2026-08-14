#!/bin/bash
# Решающая проверка: те же 4 параллельных, но с паузой 200 с — счётчик обязан истечь.
LOG=/tmp/sparse.log
CF="https://speed.cloudflare.com/__down?bytes=100000"
: > "$LOG"
for round in 1 2 3 4; do
  sleep 200
  TS=$(date -u +%H:%M:%SZ)
  for i in 1 2 3 4; do curl -sS -o /dev/null --max-time 7 -w '%{size_download}\n' "$CF" 2>/dev/null & done > /tmp/sp.tmp
  wait
  ok=$(grep -c '^100000$' /tmp/sp.tmp 2>/dev/null || echo 0)
  echo "$TS пауза200 par4=$ok/4" >> "$LOG"
  rm -f /tmp/sp.tmp
done
echo "конец" >> "$LOG"
