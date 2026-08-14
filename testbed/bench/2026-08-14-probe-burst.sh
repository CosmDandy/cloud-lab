#!/bin/bash
# Тот же тест, но БЕЗ пауз — проверка гипотезы про порог плотности соединений.
OUT=/tmp/probe-burst.log
: > "$OUT"
echo "=== серия A: 15 запросов подряд, без пауз ===" >> "$OUT"
for i in $(seq 1 15); do
  curl -sS -o /dev/null --max-time 6 \
    -w "A$i %{remote_ip} получено=%{size_download} t=%{time_total}\n" \
    "https://speed.cloudflare.com/__down?bytes=100000" >> "$OUT" 2>&1
done
echo "=== пауза 90 с (дать счётчику истечь) ===" >> "$OUT"
sleep 90
echo "=== серия B: 6 параллельных ===" >> "$OUT"
for i in $(seq 1 6); do
  curl -sS -o /dev/null --max-time 6 \
    -w "B$i %{remote_ip} получено=%{size_download} t=%{time_total}\n" \
    "https://speed.cloudflare.com/__down?bytes=100000" >> "$OUT" 2>&1 &
done
wait
echo "конец $(date -u +%H:%M:%SZ)" >> "$OUT"
