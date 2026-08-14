#!/bin/bash
# Профиль B: masquerade без обфускации, фиксированный порт 47822.
# Hopping здесь намеренно не настраивается — веб-хост, прыгающий по портам,
# сам себя выдаёт.
set -e
AUTH_PW="$1"
DOMAIN="$2"
[ -z "$AUTH_PW" ] || [ -z "$DOMAIN" ] && { echo "нужны пароль и домен"; exit 1; }

cat > /etc/hysteria/server-b.yaml <<YAML
listen: :47822

tls:
  cert: /etc/hysteria/cert.pem
  key: /etc/hysteria/key.pem

auth:
  type: password
  password: ЗАМЕНИТЬ

masquerade:
  type: proxy
  proxy:
    url: https://www.debian.org
    rewriteHost: true
YAML

pkill -f 'server-b.yaml' 2>/dev/null || true
sleep 1
setsid nohup /usr/local/bin/hysteria server -c /etc/hysteria/server-b.yaml \
  > /var/log/hysteria-b.log 2>&1 < /dev/null &
sleep 5

if ss -lnu | grep -q ':47822'; then
  echo "  профиль B поднят: UDP/47822, masquerade"
else
  echo "  FAIL:"; tail -5 /var/log/hysteria-b.log; exit 1
fi
