#!/usr/bin/env python3
"""
Собирает дашборд по метрикам, которые мы завели за эти дни.

Пишется кодом, а не руками в JSON: панелей полтора десятка, и половина из них
отличается только запросом и подписью — в редакторе это час кликов и
гарантированное расхождение стилей между панелями.
"""

import json

DS = {"type": "prometheus", "uid": "victoriametrics"}


def target(expr, legend):
    return {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": "A", "range": True}


def panel(pid, title, x, y, w, h, exprs, unit="short", desc="", stack=False, kind="timeseries"):
    custom = {
        "lineWidth": 1, "fillOpacity": 18 if stack else 8,
        "showPoints": "never", "spanNulls": True,
    }
    if stack:
        custom["stacking"] = {"mode": "normal", "group": "A"}
    return {
        "id": pid, "type": kind, "title": title, "description": desc,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {
            "defaults": {"unit": unit, "custom": custom},
            "overrides": [],
        },
        "options": {
            "legend": {"displayMode": "table", "placement": "bottom",
                       "showLegend": True, "calcs": ["lastNotNull", "max"]},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": [target(e, l) for e, l in exprs],
    }


def stat(pid, title, x, y, w, h, exprs, unit="short", desc=""):
    return {
        "id": pid, "type": "stat", "title": title, "description": desc,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {"defaults": {"unit": unit, "thresholds": {
            "mode": "absolute",
            "steps": [{"color": "green", "value": None}],
        }}, "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "textMode": "auto", "graphMode": "area"},
        "targets": [target(e, l) for e, l in exprs],
    }


def row(pid, title, y):
    return {"id": pid, "type": "row", "title": title, "collapsed": False,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []}


panels = []
y = 0

# --- Сводка -------------------------------------------------------------
panels.append(row(100, "Сводка", y)); y += 1
panels += [
    stat(1, "Живых клиентов сейчас", 0, y, 4, 4,
         [("count(count by (peer) (vpn_client_tcp_sockets > 0))", "клиентов")],
         desc="Уникальные адреса с установленными TCP-сессиями. HY2-клиенты сюда не попадают: у UDP нет соединений."),
    stat(2, "Трафик наружу", 4, y, 5, 4,
         [('sum(rate(node_network_transmit_bytes_total{device!~"lo|docker.*|veth.*|br-.*",instance=~"hhh-(sto|ams)-01"}[5m]))', "исходящий")],
         unit="Bps"),
    stat(3, "Худшая доля потерь", 9, y, 5, 4,
         [("max(100 * rate(vpn_client_tcp_retrans_bytes_total[10m]) / rate(vpn_client_tcp_sent_bytes_total[10m]))", "потери")],
         unit="percent", desc="По самому пострадавшему клиенту. Порог алерта — 10 %."),
    stat(4, "Повторов SYN в секунду", 14, y, 5, 4,
         [("sum(rate(node_netstat_TcpExt_TCPSynRetrans[10m]))", "SYN/с")],
         desc="Клиенты не могут установить соединение. Порог алерта — 10/с."),
    stat(5, "Сборщики живы", 19, y, 5, 4,
         [("sum(hy2_collector_up) + sum(xray_up)", "из 4")],
         desc="eBPF по Hysteria2 и экспорт счётчиков xray, по одному на ноду."),
]
y += 4

# --- Трафик -------------------------------------------------------------
panels.append(row(101, "Трафик", y)); y += 1
panels += [
    panel(10, "По инбаундам, отдача клиентам", 0, y, 12, 8,
          [('sum by (tag) (rate(xray_inbound_traffic_bytes_total{direction="downlink"}[5m]))', "{{tag}}")],
          unit="Bps", stack=True,
          desc="Счётчики самого xray. Видно, каким транспортом реально пользуются, а не какой настроен."),
    panel(11, "По пользователям", 12, y, 12, 8,
          [('sum by (user) (rate(xray_user_traffic_bytes_total{direction="downlink"}[5m]))', "id {{user}}")],
          unit="Bps", stack=True,
          desc="Ключ user — числовой id из панели, он же поле email в access.log."),
]
y += 8

# --- Качество -----------------------------------------------------------
panels.append(row(102, "Качество связи по клиентам", y)); y += 1
panels += [
    panel(20, "Доля потерь", 0, y, 12, 8,
          [("100 * rate(vpn_client_tcp_retrans_bytes_total[10m]) / rate(vpn_client_tcp_sent_bytes_total[10m])",
            "{{peer}} · {{inbound}}")],
          unit="percent",
          desc="Считается из счётчиков, а не берётся готовой с сокета: отношение на сокете накапливается за всю его жизнь и врёт."),
    panel(21, "RTT относительно минимума по тому же пути", 12, y, 12, 8,
          [("vpn_client_tcp_rtt_inflation", "{{peer}} · {{inbound}}")],
          desc="1 — путь свободен. 3 и выше — где-то по дороге заполняется очередь; это видно раньше, чем начнутся потери."),
    panel(22, "Повторы, оказавшиеся лишними", 0, y + 8, 12, 8,
          [("100 * rate(vpn_client_tcp_spurious_packets_total[30m]) / rate(vpn_client_tcp_retrans_packets_total[30m])",
            "{{peer}} · {{inbound}}")],
          unit="percent",
          desc="DSACK: пакет дошёл, а TCP счёл его потерянным. Высокая доля означает, что менять транспорт бесполезно — лечится настройками TCP."),
    panel(23, "Переупорядочивание", 12, y + 8, 12, 8,
          [("vpn_client_tcp_reordering", "{{peer}} · {{inbound}}")],
          desc="Оценка ядра, норма 3. Упирается в потолок tcp_max_reordering у клиентов с многопутёвым провайдером — алерта на это намеренно нет."),
]
y += 16

# --- Hysteria2 ----------------------------------------------------------
panels.append(row(103, "Hysteria2 (eBPF)", y)); y += 1
panels += [
    panel(30, "Датаграммы по клиентам", 0, y, 12, 8,
          [("rate(hy2_rx_packets_total[5m])", "{{peer}} ← приём"),
           ("rate(hy2_tx_packets_total[5m])", "{{peer}} → отдача")],
          unit="pps",
          desc="Для UDP ядро не хранит состояния потока, поэтому данные снимаются пробами eBPF на udp_queue_rcv_one_skb и udp_send_skb."),
    panel(31, "Отброшенные датаграммы", 12, y, 12, 8,
          [("rate(hy2_drops_total[5m])", "{{peer}} · {{reason}} · {{direction}}"),
           ("rate(hy2_queue_drops_total[5m])", "очередь сокета, порт {{port}}")],
          unit="pps",
          desc="Причина приходит прямо из ядра: фильтр, отсутствие сокета, переполнение очереди. Пусто — значит нода не теряет ничего своего."),
]
y += 8

# --- Восстановление TCP -------------------------------------------------
panels.append(row(104, "Как ядро справляется с потерями", y)); y += 1
panels += [
    panel(40, "Лишние повторы и потерянные повторы", 0, y, 12, 8,
          [("rate(node_tcp_dsack_received_total[15m])", "{{instance}} · повтор был лишним"),
           ("rate(node_tcp_lost_retransmit_total[15m])", "{{instance}} · потерялся сам повтор")],
          unit="cps",
          desc="Первая линия — мера того, насколько TCP ошибается; по ней оценивается эффект от tcp_reordering. Вторая — признак тяжёлых потерь."),
    panel(41, "Восстановления и таймауты", 12, y, 12, 8,
          [("rate(node_tcp_sack_recovery_total[15m])", "{{instance}} · через SACK"),
           ("rate(node_tcp_sack_recovery_fail_total[15m])", "{{instance}} · не помогло"),
           ("rate(node_tcp_timeouts_total[15m])", "{{instance}} · таймауты"),
           ("rate(node_tcp_loss_probe_recovery_total[15m])", "{{instance}} · спасено пробой хвоста")],
          unit="cps"),
]

# --- Доступность -------------------------------------------------------
# Считается из проверок gatus: у него есть и успех/неуспех, и время отклика,
# и срок сертификата. Своей метрики доступности мы не заводим — она бы
# измеряла то же самое, но с одной точки и без внешнего взгляда.
panels.append(row(105, "Доступность (SLA)", y)); y += 1
SLA_OK = 'sum by (name) (increase(gatus_results_total{success="true"}[$__range]))'
SLA_ALL = "sum by (name) (increase(gatus_results_total[$__range]))"
panels += [
    stat(50, "Худшая доступность за период", 0, y, 6, 5,
         [(f"min(100 * ({SLA_OK}) / ({SLA_ALL}))", "минимум")],
         unit="percent",
         desc="Самая проблемная проверка за выбранный период. 100 % — не упало ничего."),
    panel(51, "Доступность по проверкам", 6, y, 18, 5,
          [(f"100 * ({SLA_OK}) / ({SLA_ALL})", "{{name}}")],
          unit="percent",
          desc="Доля успешных проверок. Проседание здесь — то, что видит пользователь снаружи, а не то, что думает о себе сервер."),
    panel(52, "Время отклика проверок", 0, y + 5, 12, 7,
          [("gatus_results_duration_seconds", "{{name}}")],
          unit="s",
          desc="Сколько занимает сама проверка. Рост до того, как она начнёт падать, — самый ранний признак беды."),
    panel(53, "Дней до истечения сертификатов", 12, y + 5, 12, 7,
          [("gatus_results_certificate_expiration_seconds / 86400", "{{name}}")],
          unit="d",
          desc="Let's Encrypt обновляет за 30 дней до конца. Линия, ушедшая ниже 20, означает, что обновление не отработало."),
]
y += 12

dashboard = {
    "uid": "vpn-traffic-quality",
    "title": "VPN: трафик и качество",
    "description": "Трафик по инбаундам и пользователям, потери и RTT по каждому клиенту, Hysteria2 из eBPF, работа восстановления TCP.",
    "tags": ["vpn", "traffic"],
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 1,
    "refresh": "1m",
    "time": {"from": "now-6h", "to": "now"},
    "editable": True,
    "panels": panels,
    "templating": {"list": []},
}

path = "ansible/roles/observability/files/grafana/dashboards/vpn-traffic.json"
with open(path, "w", encoding="utf-8") as fh:
    json.dump(dashboard, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
print("панелей:", len([p for p in panels if p["type"] != "row"]), "| рядов:", len([p for p in panels if p["type"] == "row"]))
