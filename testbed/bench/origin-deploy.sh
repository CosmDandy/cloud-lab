#!/usr/bin/env bash
# Разворачивает (или гасит) приёмник боевого стенда на нодах.
#
# Запускается с машины, у которой есть ssh к нодам, — не с той, что меряет:
# у замеряющей машины ssh к проду нет и быть не должно. Порт 18080 открыт
# декларативно в group_vars/vpn_nodes/vars.yaml; здесь только слушатель,
# который живёт ровно на время прогона.
#
#   origin-deploy.sh up   hhh-sto-01 hhh-ams-01 hhh-osl-01
#   origin-deploy.sh down hhh-sto-01 hhh-ams-01 hhh-osl-01
set -euo pipefail

ACTION="${1:?up | down}"
shift
[ "$#" -gt 0 ] || { echo "нужен хотя бы один хост"; exit 1; }

SRC="$(cd "$(dirname "$0")" && pwd)/local-origin.py"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=5 -T)
# Имена хостов могут жить в отдельном конфиге, а не в ~/.ssh/config: ноды
# отвечают на нестандартном порту и под своим ключом.
[ -n "${SSH_CONFIG:-}" ] && SSH_OPTS+=(-F "$SSH_CONFIG")
PORT="${ORIGIN_PORT:-18080}"

for HOST in "$@"; do
    case "$ACTION" in
        up)
            scp "${SSH_OPTS[@]}" "$SRC" "$HOST:/usr/local/bin/bench-origin.py" >/dev/null
            ssh "${SSH_OPTS[@]}" "$HOST" "
                chmod +x /usr/local/bin/bench-origin.py
                systemctl stop bench-origin 2>/dev/null || true
                systemd-run --unit=bench-origin --collect \
                    /usr/bin/python3 /usr/local/bin/bench-origin.py $PORT >/dev/null
            "
            echo "$HOST: приёмник на :$PORT поднят"
            ;;
        down)
            ssh "${SSH_OPTS[@]}" "$HOST" "
                systemctl stop bench-origin 2>/dev/null || true
                rm -f /usr/local/bin/bench-origin.py
            "
            echo "$HOST: приёмник снят"
            ;;
        *)
            echo "неизвестное действие: $ACTION"; exit 1
            ;;
    esac
done
