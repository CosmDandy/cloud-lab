#!/usr/bin/env bash
# Боевой стенд: скорость до РЕАЛЬНЫХ нод через реальные инбаунды.
#
# Чем отличается от run-all.sh. Тот поднимает xray-сервер и xray-клиент на
# одной машине и меряет оверхед транспорта — трафик там не покидает петлю.
# Здесь клиент берёт ту же ссылку, что получает живой пользователь, идёт
# через Стокгольм, Амстердам или Осло и упирается в то же, во что упирается
# он: канал офиса, RTT до ноды, поведение протокола на реальном пути.
#
# Приёмник стоит на самой ноде (:18080, поднимается bench/origin-deploy.sh с
# управляющей машины). Так и прямой замер, и замер через туннель идут одним
# путём офис↔нода и сравнимы между собой; трафик, который нода шлёт на
# собственный публичный адрес, ядро заворачивает локально, поэтому внешний
# канал занимает только туннель — то, что и меряем.
#
# Почему не внешнее зеркало: speed.cloudflare.com режет серию запросов по
# объёму (429) — 11.09.2026 так терялось до пяти замеров из шести, — а
# зеркала, которые отдают файл, не принимают POST, из-за чего upload (то
# единственное, чем stream-up отличается от packet-up) не измерить вовсе.
#
# Использование — с машины, чьим каналом меряем; ssh к проду ей не нужен:
#   SUB_URL=https://sub.example/<uuid> prod-matrix.sh
#   SUB_URL=... prod-matrix.sh "HHH-STO"          # только Стокгольм
#   PARALLEL=8 SUB_URL=... prod-matrix.sh         # канал, а не транспорт
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

SUB_URL="${SUB_URL:?нужен SUB_URL — ссылка на подписку или файл с ней}"
ORIGIN_PORT="${ORIGIN_PORT:-18080}"
XRAY_IMAGE="${XRAY_IMAGE:-ghcr.io/xtls/xray-core:latest}"
SOCKS_PORT="${SOCKS_PORT:-10808}"
DL_BYTES="${DOWNLOAD_BYTES:-52428800}"
UL_BYTES="${UPLOAD_BYTES:-26214400}"

# Подписка не отдаёт salamander-пароль и диапазон порт-хоппинга: в панели у
# всех HY2-хостов пусто поле final_mask. Без этих двух значений HY2
# Salamander и HY2 Hop не подключаются в принципе — что прогон и показывает.
# Передав их здесь, можно отделить «протокол сломан» от «подписка не отдала
# параметр».
HY2_SALAMANDER="${HY2_SALAMANDER:-}"
HY2_HOP_PORTS="${HY2_HOP_PORTS:-}"

DATE="$(date +%F)"
RESULTS_DIR="${RESULTS_DIR:-results/$DATE-prod}"
mkdir -p "$RESULTS_DIR"

cleanup() {
    docker rm -f xray-prod-cli >/dev/null 2>&1 || true
}
trap cleanup EXIT

slug() {
    printf '%s' "$1" \
        | sed -e 's/[^A-Za-z0-9]\+/-/g' -e 's/^-//' -e 's/-$//' \
        | tr '[:upper:]' '[:lower:]'
}

# remark → host:port ссылки. Приёмник ищем по тому же адресу, на который
# смотрит инбаунд: так замер и его знаменатель гарантированно про одну ноду.
LISTING="$(python3 "$ROOT/sub2client.py" "$SUB_URL" --list)"

host_of() {
    printf '%s\n' "$LISTING" | awk -F'\t' -v r="$1" '$1 == r { split($4, a, ":"); print a[1]; exit }'
}

mapfile -t REMARKS < <(printf '%s\n' "$LISTING" | cut -f1)
if [ "$#" -gt 0 ]; then
    FILTERED=()
    for r in "${REMARKS[@]}"; do
        for pat in "$@"; do
            case "$r" in *"$pat"*) FILTERED+=("$r");; esac
        done
    done
    REMARKS=("${FILTERED[@]:-}")
fi
[ "${#REMARKS[@]}" -eq 0 ] || [ -z "${REMARKS[0]}" ] && [ "${#REMARKS[@]}" -le 1 ] && {
    echo "ни один хост не выбран"; exit 1
}

echo "==> Боевой стенд $DATE — ${#REMARKS[@]} хост(ов), приёмник :$ORIGIN_PORT на нодах"
echo

# Прямой канал до каждой ноды: без него цифра через туннель не с чем
# сравнить, и медленный протокол не отличить от медленного канала.
declare -A BASE_OF
baseline_for() {
    local node="$1"
    [ -n "${BASE_OF[$node]:-}" ] && return 0
    local speed
    speed=$(curl -sS -o /dev/null --max-time 120 -w "%{speed_download}" \
        "http://$node:$ORIGIN_PORT/__down?bytes=$DL_BYTES" 2>/dev/null || echo 0)
    BASE_OF[$node]=$(printf '%.0f' "${speed:-0}")
    echo "baseline_direct_bytes_s=${BASE_OF[$node]}" > "$RESULTS_DIR/baseline-$(slug "$node").raw"
    echo "    прямой канал до $node: ${BASE_OF[$node]} байт/с"
}

for REMARK in "${REMARKS[@]}"; do
    [ -z "$REMARK" ] && continue
    NAME="$(slug "$REMARK")"
    NODE="$(host_of "$REMARK")"
    ORIGIN="http://$NODE:$ORIGIN_PORT"
    echo "---"
    echo "[*] $REMARK  →  $NODE"

    # Приёмник поднимается снаружи; без проверки прогон намерил бы нули и
    # выглядел бы как «протокол не тянет».
    if ! curl -sS -o /dev/null --max-time 8 "$ORIGIN/__down?bytes=1024" 2>/dev/null; then
        echo "  ! приёмник на $NODE:$ORIGIN_PORT недоступен — пропуск"
        echo "    подними его: bench/origin-deploy.sh up <хост>"
        {
            echo "remark=$REMARK"
            echo "status=origin-down"
        } > "$RESULTS_DIR/${NAME}.raw"
        continue
    fi
    baseline_for "$NODE"

    ARGS=(--select "$REMARK" --socks-port "$SOCKS_PORT")
    case "$REMARK" in
        *Salamander*|*Hop*)
            [ -n "$HY2_SALAMANDER" ] && ARGS+=(--salamander "$HY2_SALAMANDER")
            ;;
    esac
    case "$REMARK" in
        *Hop*) [ -n "$HY2_HOP_PORTS" ] && ARGS+=(--hop-ports "$HY2_HOP_PORTS");;
    esac

    CFG="$(mktemp)"
    if ! python3 "$ROOT/sub2client.py" "$SUB_URL" "${ARGS[@]}" > "$CFG"; then
        echo "  ! не собрался конфиг — пропуск"
        rm -f "$CFG"
        continue
    fi
    # mktemp отдаёт 0600, а xray в контейнере работает не от root: без этого
    # он падает на "permission denied", и прогон выглядит как «протокол не
    # поднялся».
    chmod 644 "$CFG"

    docker rm -f xray-prod-cli >/dev/null 2>&1 || true
    docker run -d --name xray-prod-cli --network host \
        -v "$CFG:/etc/xray/config.json:ro" \
        "$XRAY_IMAGE" -c /etc/xray/config.json >/dev/null

    # Клиент должен именно отвечать через прокси: контейнер, упавший на
    # разборе конфига, оставляет порт закрытым, и бенчмарк намерил бы нули.
    UP="no"
    for _ in $(seq 1 20); do
        if curl -sS -o /dev/null --max-time 3 --proxy "socks5h://127.0.0.1:$SOCKS_PORT" \
            "$ORIGIN/__down?bytes=1024" 2>/dev/null; then
            UP="yes"; break
        fi
        sleep 0.5
    done

    RAW="$RESULTS_DIR/${NAME}.raw"
    if [ "$UP" != "yes" ]; then
        echo "  ! прокси не поднялся"
        {
            echo "remark=$REMARK"
            echo "status=proxy-down"
            echo "xray_log:"
            docker logs xray-prod-cli 2>&1 | tail -10
        } > "$RAW"
        docker rm -f xray-prod-cli >/dev/null 2>&1 || true
        rm -f "$CFG"
        continue
    fi

    {
        echo "remark=$REMARK"
        echo "node=$NODE"
        echo "parallel=${PARALLEL:-1}"
        echo "baseline_direct_bytes_s=${BASE_OF[$NODE]}"
        URL="$ORIGIN" UP_URL="$ORIGIN" DL_GAP="${DL_GAP:-0}" \
            DOWNLOAD_BYTES="$DL_BYTES" UPLOAD_BYTES="$UL_BYTES" \
            bash "$ROOT/bench/benchmark.sh" "$NAME"
    } > "$RAW" 2>&1 || echo "  ! бенчмарк отработал с ошибкой, см. $RAW"

    grep -E '^(dl_avg_bytes_s|ul_avg_bytes_s|dl_fails|ul_fails)=' "$RAW" | sed 's/^/    /' || true

    docker rm -f xray-prod-cli >/dev/null 2>&1 || true
    rm -f "$CFG"
done

echo "---"
python3 "$ROOT/bench/prod-summary.py" "$RESULTS_DIR"
echo "==> Готово: $RESULTS_DIR/"
