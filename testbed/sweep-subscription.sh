#!/usr/bin/env bash
# Прогоняет каждый хост подписки как настоящий клиент.
#
# Правка в панели может выглядеть применённой со всех сторон — порт слушает,
# TLS отвечает, ноды подключены — и всё равно раздавать клиенту негодные
# параметры: подписка собирается не из конфига xray, а из таблицы панели, и
# эти двое расходятся молча. Единственная проверка, которая это ловит, —
# собрать клиента из живой подписки и залить через него трафик.
#
#     ./sweep-subscription.sh <url подписки> [байт]
set -u
SUB="${1:?нужен url подписки}"
BYTES="${2:-20000000}"

# --list отдаёт «имя<TAB>протокол<TAB>транспорт<TAB>адрес» — нужно только имя
names=$(python3 /tmp/sub2client.py "$SUB" --list 2>/dev/null | cut -f1 | sort) || {
    echo "не удалось прочитать подписку"
    exit 1
}

fail=0
while IFS= read -r name; do
    [ -z "$name" ] && continue
    cfg=$(mktemp /tmp/sweep-XXXX.json)
    if ! python3 /tmp/sub2client.py "$SUB" --select "$name" >"$cfg" 2>/dev/null; then
        printf '  %-34s не собрался\n' "$name"
        rm -f "$cfg"
        fail=$((fail + 1))
        continue
    fi

    /tmp/xr2699/xray run -c "$cfg" >/dev/null 2>&1 &
    pid=$!
    sleep 3

    out=$(curl -sS --max-time 45 -o /dev/null -x socks5h://127.0.0.1:10808 \
        -w '%{speed_download}' "https://speed.cloudflare.com/__down?bytes=$BYTES" 2>/dev/null)
    kill $pid 2>/dev/null
    wait $pid 2>/dev/null
    rm -f "$cfg"

    mbps=$(awk -v b="${out:-0}" 'BEGIN{printf "%.0f", b*8/1e6}')
    if [ "${mbps:-0}" -gt 0 ]; then
        printf '  %-34s %5s Мбит/с\n' "$name" "$mbps"
    else
        printf '  %-34s НЕ РАБОТАЕТ\n' "$name"
        fail=$((fail + 1))
    fi
done <<<"$names"

echo
if [ "$fail" -gt 0 ]; then
    echo "нерабочих хостов: $fail"
    exit 1
fi
echo "все хосты отвечают"
