#!/usr/bin/env bash
# Single-variant benchmark through xray-cli's SOCKS5 (default localhost:10808).
# Output: machine-readable lines `KEY=value`. The run-all.sh wrapper parses and aggregates.
#
# Usage:
#   benchmark.sh <variant-name>
set -euo pipefail

VARIANT="${1:?variant name required}"
PROXY="${PROXY:-socks5h://127.0.0.1:10808}"
URL="${URL:-https://speed.cloudflare.com}"
# Приёмник загрузки может отличаться от источника скачивания: публичные
# зеркала отдают файлы, но не принимают POST. Без замера upload не отличить
# XHTTP stream-up от packet-up — а различаются они именно им.
UP_URL="${UP_URL:-$URL}"
# Сколько одновременных соединений держать при замере скорости.
# 1 мерит транспорт: один поток упирается в окно/RTT, а не в канал, и
# протоколы сравниваются на равных. Больше — мерит канал так, как его
# видит браузер, который открывает соединения десятками.
PARALLEL="${PARALLEL:-1}"
# 25 МБ, а не 200: 11.09.2026 speed.cloudflare.com стал отвечать 403 на
# /__down с bytes больше ~26 МБ. Прежний дефолт не падал, а тихо возвращал
# нулевую скорость — весь прогон выглядел рабочим и мерил мусор.
DL_BYTES="${DOWNLOAD_BYTES:-26214400}"
UL_BYTES="${UPLOAD_BYTES:-50000000}"
REPEATS="${REPEATS:-3}"

# Curl baseline opts
C="curl -sS --proxy $PROXY --max-time 120"

# Pre-warm Reality handshake (TLS-in-TLS not measured for first hit)
$C -o /dev/null "$URL/cdn-cgi/trace" >/dev/null 2>&1 || true
sleep 1

emit() { printf '%s=%s\n' "$1" "$2"; }

emit variant "$VARIANT"
emit timestamp "$(date -Iseconds)"

# 1. Handshake metrics (single small request)
HS=$($C -o /dev/null -w "tcp=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total} httpcode=%{http_code}" \
     "$URL/__down?bytes=1024" 2>&1) || HS="error=connect-fail"
emit "handshake_raw" "$HS"

# 2. Download throughput
DL_TOTAL=0
DL_MAX=0
DL_FAILS=0
# Код ответа проверяется наравне со скоростью: speed.cloudflare.com отдаёт
# 429 Too Many Requests при серийных запросах, и это выглядит как «загрузка
# со скоростью 9 байт в секунду» — curl отработал без ошибки, тело в 1 байт.
# 11.09.2026 так терялось до пяти замеров из шести, а разброс внутри одного
# варианта доходил до 91 %: сравнивались не транспорты, а везение.
#
# DL_GAP — пауза между прогонами, чтобы не выбирать лимит.
DL_GAP="${DL_GAP:-10}"

# Один прогон = PARALLEL одновременных скачиваний, скорости складываются.
# Печатает суммарные байты/с либо причину отказа: одно отвергнутое соединение
# портит весь прогон, потому что остальные поделят между собой канал, который
# должен был делиться на всех.
dl_once() {
    local dir j
    dir=$(mktemp -d)
    for j in $(seq 1 "$PARALLEL"); do
        (
            $C -o /dev/null -w "%{speed_download} %{http_code} %{size_download}" \
                "$URL/__down?bytes=$DL_BYTES" 2>/dev/null > "$dir/$j" || echo "0 000 0" > "$dir/$j"
        ) &
    done
    wait
    awk -v want="$DL_BYTES" '
        { if ($2 != "200" || $3 + 0 < want) { bad = $2 "-" $3 "B" } ; sum += $1 }
        END { if (bad != "") print "rejected-http" bad; else printf "%.0f\n", sum }
    ' "$dir"/*
    rm -rf "$dir"
}

for i in $(seq 1 "$REPEATS"); do
    [ "$i" -gt 1 ] && [ "$DL_GAP" != "0" ] && sleep "$DL_GAP"
    RESULT=$(dl_once)
    case "$RESULT" in
        rejected-*)
            DL_FAILS=$((DL_FAILS+1))
            emit "dl_run_$i" "$RESULT"
            continue
            ;;
    esac
    emit "dl_run_$i" "$RESULT"
    DL_TOTAL=$((DL_TOTAL + RESULT))
    [ "$RESULT" -gt "$DL_MAX" ] && DL_MAX=$RESULT
done
GOOD_DL=$((REPEATS - DL_FAILS))
if [ "$GOOD_DL" -gt 0 ]; then
    emit "dl_avg_bytes_s" "$((DL_TOTAL / GOOD_DL))"
    emit "dl_max_bytes_s" "$DL_MAX"
fi
emit "dl_fails" "$DL_FAILS"

# 3. Upload throughput (random bytes from /dev/urandom)
UL_TOTAL=0
UL_MAX=0
UL_FAILS=0
TMPFILE=$(mktemp)
head -c "$UL_BYTES" /dev/urandom > "$TMPFILE"

ul_once() {
    local dir j
    dir=$(mktemp -d)
    for j in $(seq 1 "$PARALLEL"); do
        (
            $C -X POST --data-binary "@$TMPFILE" -o /dev/null -w "%{speed_upload} %{http_code}" \
                "$UP_URL/__up" 2>/dev/null > "$dir/$j" || echo "0 000" > "$dir/$j"
        ) &
    done
    wait
    awk '
        { if ($2 != "200") { bad = $2 } ; sum += $1 }
        END { if (bad != "") print "rejected-http" bad; else printf "%.0f\n", sum }
    ' "$dir"/*
    rm -rf "$dir"
}

for i in $(seq 1 "$REPEATS"); do
    RESULT=$(ul_once)
    case "$RESULT" in
        rejected-*)
            UL_FAILS=$((UL_FAILS+1))
            emit "ul_run_$i" "$RESULT"
            continue
            ;;
    esac
    emit "ul_run_$i" "$RESULT"
    UL_TOTAL=$((UL_TOTAL + RESULT))
    [ "$RESULT" -gt "$UL_MAX" ] && UL_MAX=$RESULT
done
rm -f "$TMPFILE"
GOOD_UL=$((REPEATS - UL_FAILS))
if [ "$GOOD_UL" -gt 0 ]; then
    emit "ul_avg_bytes_s" "$((UL_TOTAL / GOOD_UL))"
    emit "ul_max_bytes_s" "$UL_MAX"
fi
emit "ul_fails" "$UL_FAILS"

# 4. Connectivity / target metadata
META=$($C "$URL/meta" 2>/dev/null) || META="{}"
emit "cf_meta" "$(echo "$META" | tr '\n' ' ')"

# 5. Connection freezing probe — small payloads at 5/16/50 KB
for BYTES in 5000 16000 50000; do
    OK="ok"
    $C -o /dev/null --max-time 10 "$URL/__down?bytes=$BYTES" >/dev/null 2>&1 || OK="fail"
    emit "freeze_${BYTES}" "$OK"
done
