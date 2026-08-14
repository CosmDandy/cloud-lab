#!/bin/bash
# Сертификат Let's Encrypt через HTTP-01. Секретов не требует: валидация идёт
# по 80 порту, который на нодах свободен. Порт занимается только на время
# выпуска и сразу освобождается.
set -e
DOMAIN="$1"
EMAIL="${2:-tkondrashin@icloud.com}"
[ -z "$DOMAIN" ] && { echo "нужен домен первым аргументом"; exit 1; }

if [ ! -x /usr/local/bin/lego ]; then
  URL=$(curl -sS --max-time 20 https://api.github.com/repos/go-acme/lego/releases/latest \
        | grep -o '"browser_download_url": "[^"]*"' | cut -d'"' -f4 \
        | grep 'linux_amd64.tar.gz$' | head -1)
  echo "качаю: $URL"
  curl -sSL --max-time 120 -o /tmp/lego.tar.gz "$URL"
  tar -xzf /tmp/lego.tar.gz -C /tmp lego
  install -m755 /tmp/lego /usr/local/bin/lego
fi
/usr/local/bin/lego --version | head -1

mkdir -p /etc/hysteria
/usr/local/bin/lego run \
  --accept-tos \
  --email "$EMAIL" \
  --http \
  --http.address :80 \
  --domains "$DOMAIN" \
  --path /etc/lego 2>&1 | tail -6

install -m644 "/etc/lego/certificates/${DOMAIN}.crt" /etc/hysteria/cert.pem
install -m600 "/etc/lego/certificates/${DOMAIN}.key" /etc/hysteria/key.pem
echo "--- сертификат ---"
openssl x509 -in /etc/hysteria/cert.pem -noout -subject -issuer -dates | sed 's/^/  /'
