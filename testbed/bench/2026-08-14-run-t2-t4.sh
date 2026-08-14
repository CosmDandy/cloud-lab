#!/bin/bash
# T2 (порог параллельности), T3 (длительность заморозки), T4 (к чему привязана).
# Только чтение. Паузы длинные намеренно — счётчику надо истечь.
OUT=/tmp/t2-t4.log
URL="https://speed.cloudflare.com/__down?bytes=100000"
: > "$OUT"

say() { echo "$*" >> "$OUT"; }
probe() { curl -sS -o /dev/null --max-time 8 -w "$1 получено=%{size_download} t=%{time_total}\n" "$URL" >> "$OUT" 2>&1; }

say "=== T2: порог параллельности, $(date -u +%H:%M:%SZ) ==="
for n in 2 3 4 5; do
  say "--- $n параллельных ---"
  for i in $(seq 1 "$n"); do probe "n=$n#$i" & done
  wait
  say "(пауза 150 с)"
  sleep 150
done

say ""
say "=== T3: длительность заморозки, $(date -u +%H:%M:%SZ) ==="
say "--- триггер: 6 параллельных ---"
for i in $(seq 1 6); do probe "trig#$i" & done
wait
for k in 1 2 3 4 5 6 7 8; do
  sleep 15
  probe "t+$((k*15))c"
done

say ""
say "=== T4: к чему привязана заморозка, $(date -u +%H:%M:%SZ) ==="
say "--- повторный триггер ---"
for i in $(seq 1 6); do probe "trig2#$i" & done
wait
curl -sS -o /dev/null --max-time 8 -w "тот же SNI: получено=%{size_download}\n" "$URL" >> "$OUT" 2>&1
curl -sS -o /dev/null --max-time 8 -w "другой SNI на CF: получено=%{size_download}\n" "https://cloudflare.com/cdn-cgi/trace" >> "$OUT" 2>&1
curl -sS -o /dev/null --max-time 8 --insecure -w "своя нода sto-02: получено=%{size_download} код=%{http_code}\n" "https://167.104.104.209/" >> "$OUT" 2>&1
curl -sS -o /dev/null --max-time 8 --insecure -w "своя нода sto-01: получено=%{size_download} код=%{http_code}\n" "https://167.104.104.131/" >> "$OUT" 2>&1

say ""
say "конец $(date -u +%H:%M:%SZ)"
