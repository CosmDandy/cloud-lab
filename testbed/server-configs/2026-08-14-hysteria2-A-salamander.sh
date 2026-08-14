#!/bin/bash
# Боевой профиль Hysteria2 на ноде: порт 47821, salamander, masquerade proxy,
# port hopping 47000-47100 через nftables. BBR (bandwidth не задан).
set -e
AUTH_PW="$1"
OBFS_PW="$2"
[ -z "$AUTH_PW" ] || [ -z "$OBFS_PW" ] && { echo "нужны два пароля аргументами"; exit 1; }

cat > /etc/hysteria/server.yaml <<YAML
listen: :47821

tls:
  cert: /etc/hysteria/cert.pem
  key: /etc/hysteria/key.pem

auth:
  type: password
  password: ЗАМЕНИТЬ

obfs:
  type: salamander
  salamander:
    password: ЗАМЕНИТЬ

masquerade:
  type: proxy
  proxy:
    url: https://www.debian.org
    rewriteHost: true
YAML

pkill -f 'hysteria server' 2>/dev/null || true
sleep 1
setsid nohup /usr/local/bin/hysteria server -c /etc/hysteria/server.yaml \
  > /var/log/hysteria.log 2>&1 < /dev/null &
sleep 5

if ss -lnu | grep -q ':47821'; then
  echo "OK: слушает UDP/47821"
else
  echo "FAIL:"; tail -5 /var/log/hysteria.log; exit 1
fi

# port hopping: диапазон 47000-47100 заворачивается на рабочий порт
if command -v nft >/dev/null; then
  nft list table ip hyhop >/dev/null 2>&1 && nft delete table ip hyhop
  nft add table ip hyhop
  nft add chain ip hyhop prerouting '{ type nat hook prerouting priority dstnat; }'
  nft add rule ip hyhop prerouting udp dport 47000-47100 redirect to :47821
  echo "OK: hopping 47000-47100 -> 47821"
else
  echo "nft отсутствует, hopping не настроен"
fi
