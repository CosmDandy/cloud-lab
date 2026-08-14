#!/bin/bash
# Ежечасный замер домашнего канала. Только чтение.
LOG=/home/cosmdandy/probe-hourly.log
TS=$(date -u +%Y-%m-%dT%H:%MZ)
ok=0; bad=0
for i in $(seq 1 10); do
  sz=$(curl -sS -o /dev/null --max-time 8 -w '%{size_download}' \
       "https://speed.cloudflare.com/__down?bytes=100000" 2>/dev/null)
  if [ "$sz" = "100000" ]; then ok=$((ok+1)); else bad=$((bad+1)); fi
  sleep 2
done
echo "$TS последовательных: ok=$ok bad=$bad" >> "$LOG"
# порог параллельности: 3 (должно проходить) и 4 (должно падать)
for n in 3 4; do
  res=0
  for i in $(seq 1 $n); do
    curl -sS -o /dev/null --max-time 8 -w '%{size_download}\n' \
      "https://speed.cloudflare.com/__down?bytes=100000" 2>/dev/null &
  done > /tmp/par-$n.tmp
  wait
  res=$(grep -c '^100000$' /tmp/par-$n.tmp 2>/dev/null || echo 0)
  echo "$TS параллельных $n: прошло $res из $n" >> "$LOG"
  rm -f /tmp/par-$n.tmp
  sleep 150
done
