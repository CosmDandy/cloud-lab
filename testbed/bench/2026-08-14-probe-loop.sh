#!/bin/bash
# Замер порога обрыва с домашнего канала. Только чтение, ничего не меняет.
OUT=/tmp/probe-cf.log
: > "$OUT"
echo "старт $(date -u +%H:%M:%SZ)" >> "$OUT"
for i in $(seq 1 30); do
  curl -sS -o /dev/null --max-time 6 \
    -w "$i %{remote_ip} получено=%{size_download} код=%{http_code} t=%{time_total}\n" \
    "https://speed.cloudflare.com/__down?bytes=100000" >> "$OUT" 2>&1
  sleep 1
done
echo "конец $(date -u +%H:%M:%SZ)" >> "$OUT"
