#!/usr/bin/env python3
"""
Собирает оба VPN-дашборда: «трафик и качество» и «здоровье нод».

Пишется кодом, а не руками в JSON: панелей полтора десятка, и половина из них
отличается только запросом и подписью — в редакторе это час кликов и
гарантированное расхождение стилей между панелями.

Запуск из корня репозитория: python3 ansible/roles/observability/files/grafana/mkdash.py
"""

import json
import re

DS = {"type": "prometheus", "uid": "victoriametrics"}
OUT = "ansible/roles/observability/files/grafana/dashboards"

# Metrics a VPN node pushes itself: `instance` is the node name, so the "Нода"
# selector narrows them directly. The panel's remnawave_* series carry the node
# only as node_name on remnawave_node_basic_info, and every one of them joins
# through it. gatus, the probe and the peer-users lookups are not per node and
# stay as they are.
NODE_METRICS = {
    "hy2_collector_up",
    "hy2_drops_total",
    "hy2_rx_bytes_total",
    "hy2_tx_bytes_total",
    "node_netstat_TcpExt_TCPSynRetrans",
    "node_netstat_Tcp_OutSegs",
    "node_netstat_Tcp_RetransSegs",
    "node_netstat_Udp_RcvbufErrors",
    "node_network_transmit_bytes_total",
    "node_tcp_dsack_received_total",
    "node_tcp_lost_retransmit_total",
    "vpn_client_tcp_retrans_bytes_total",
    "vpn_client_tcp_rtt_ms",
    "vpn_client_tcp_sent_bytes_total",
    "xray_inbound_traffic_bytes_total",
    "xray_up",
    "xray_user_traffic_bytes_total",
}
NODE_MATCHER = {m: 'instance=~"$node"' for m in NODE_METRICS}
NODE_MATCHER["remnawave_node_basic_info"] = 'node_name=~"$node"'
SELECTOR = re.compile(
    r'(?<![\w"])(' + "|".join(sorted(NODE_MATCHER)) + r')(?![\w"])(\{[^}]*\})?'
)

NODE_VAR = {
    "name": "node",
    "label": "Нода",
    "type": "query",
    "datasource": DS,
    "definition": "label_values(xray_up, instance)",
    "query": {"query": "label_values(xray_up, instance)", "refId": "node"},
    "multi": True,
    "includeAll": True,
    "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
    "refresh": 2,
    "sort": 1,
}


def scoped(expr):
    """Add the node selector to every per-node metric in expr."""

    def add(m):
        matcher = NODE_MATCHER[m.group(1)]
        inner = (m.group(2) or "{}")[1:-1].strip()
        return f"{m.group(1)}{{{matcher}{', ' + inner if inner else ''}}}"

    return SELECTOR.sub(add, expr)

# Same volume gate as the alerts in vmalert/alerts.yaml: below 64 KiB/s a
# connection is mostly idle, and a share computed from a few retransmitted
# bytes over a few sent ones reads as "100 % loss" while nobody suffers.
ACTIVE_BPS = 65536

# Collectors push every 30 s. Gaps shorter than this are glitches and get
# bridged; longer ones are real absences (client gone, node down) and must stay
# visible instead of being drawn over with a straight line.
SPAN_MS = 300000


def target(expr, legend, interval=None):
    t = {
        "datasource": DS,
        "expr": expr,
        "legendFormat": legend,
        "refId": "A",
        "range": True,
    }
    if interval:
        t["interval"] = interval
    return t


def panel(
    pid,
    title,
    x,
    y,
    w,
    h,
    exprs,
    unit="short",
    desc="",
    stack=False,
    kind="timeseries",
    calcs=("mean", "max"),
    bars=False,
    interval=None,
    decimals=None,
    minimum=None,
):
    custom = {
        "lineWidth": 1,
        "fillOpacity": 18 if stack or bars else 8,
        "showPoints": "never",
        "spanNulls": SPAN_MS,
    }
    if bars:
        custom["drawStyle"] = "bars"
        custom["fillOpacity"] = 80
    if stack:
        custom["stacking"] = {"mode": "normal", "group": "A"}
    defaults = {"unit": unit, "custom": custom}
    if decimals is not None:
        defaults["decimals"] = decimals
    if minimum is not None:
        defaults["min"] = minimum
    return {
        "id": pid,
        "type": kind,
        "title": title,
        "description": desc,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "legend": {
                "displayMode": "table",
                "placement": "bottom",
                "showLegend": True,
                "calcs": list(calcs),
            },
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": [
            dict(target(e, leg, interval), refId=chr(65 + i))
            for i, (e, leg) in enumerate(exprs)
        ],
    }


def stat(
    pid,
    title,
    x,
    y,
    w,
    h,
    exprs,
    unit="short",
    desc="",
    steps=None,
    decimals=None,
    instant=False,
    mappings=None,
):
    defaults = {
        "unit": unit,
        "thresholds": {
            "mode": "absolute",
            "steps": steps or [{"color": "green", "value": None}],
        },
    }
    if decimals is not None:
        defaults["decimals"] = decimals
    if mappings:
        defaults["mappings"] = mappings
    targets = []
    for i, (e, leg) in enumerate(exprs):
        t = dict(target(e, leg), refId=chr(65 + i))
        if instant:
            t.update({"instant": True, "range": False})
        targets.append(t)
    return {
        "id": pid,
        "type": "stat",
        "title": title,
        "description": desc,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "auto",
            "colorMode": "background",
            "graphMode": "none" if instant else "area",
        },
        "targets": targets,
    }


def timeline(pid, title, x, y, w, h, exprs, desc="", mappings=None, interval=None):
    """State timeline: one lane per series, colour by value mapping."""
    return {
        "id": pid,
        "type": "state-timeline",
        "title": title,
        "description": desc,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {
            "defaults": {
                "mappings": mappings or [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "red", "value": None},
                        {"color": "yellow", "value": 0.5},
                        {"color": "green", "value": 0.99},
                    ],
                },
                "color": {"mode": "thresholds"},
            },
            "overrides": [],
        },
        "options": {
            "showValue": "never",
            "mergeValues": True,
            "rowHeight": 0.8,
            "legend": {"showLegend": False},
        },
        "targets": [
            dict(target(e, leg, interval), refId=chr(65 + i))
            for i, (e, leg) in enumerate(exprs)
        ],
    }


def row(pid, title, y):
    return {
        "id": pid,
        "type": "row",
        "title": title,
        "collapsed": False,
        "gridPos": {"x": 0, "y": y, "w": 24, "h": 1},
        "panels": [],
    }


# Client series carry only `peer` (an IP) and xray's own carry `user` (a panel
# id). vpn_peer_user / vpn_user_info from the peer-users exporter put a name on
# both. The `unless` branch keeps a series visible, nameless, when the lookup
# has not seen it — a plain join would make it vanish from the graph.
def named(expr):
    return (
        f"({expr}) * on (peer) group_left (username) vpn_peer_user"
        f" or (({expr}) unless on (peer) vpn_peer_user)"
    )


def named_user(expr):
    return (
        f"({expr}) * on (user) group_left (username) vpn_user_info"
        f" or (({expr}) unless on (user) vpn_user_info)"
    )


# Only VPN nodes run xray_up; joining on it keeps the control plane (which
# also pushes node-exporter) out without a hard-coded host list.
def vpn_nodes(expr):
    return f"({expr}) and on (instance) xray_up"


EGRESS = (
    "rate(node_network_transmit_bytes_total"
    '{device!~"lo|docker.*|veth.*|br-.*|amn.*|awg.*|wg.*"}[5m])'
)


# Counted against the panel's node list, so a node that stopped pushing
# altogether shows up too, not only one that reports a collector as down.
def nodes_without(metric):
    return f"(count(remnawave_node_basic_info) - (count({metric} == 1) or vector(0)))"


# sto-03/04 carry per-node copies of the inbounds with a -STO3/-STO4 suffix;
# for "which transport do people use" they are the same transport.
def base_tag(expr):
    return f'label_replace({expr}, "tag", "$1", "tag", "(.*?)(-STO[0-9]+)?")'


def table(pid, title, x, y, w, h, columns, desc=""):
    """Instant queries merged into one row per label set; columns: (expr, header, unit)."""
    return {
        "id": pid,
        "type": "table",
        "title": title,
        "description": desc,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {
            "defaults": {},
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": header},
                    "properties": [
                        {"id": "unit", "value": unit},
                        {"id": "decimals", "value": 1},
                    ],
                }
                for _, header, unit in columns
            ],
        },
        "options": {
            "showHeader": True,
            "sortBy": [{"displayName": columns[0][1], "desc": True}],
        },
        "targets": [
            {
                "datasource": DS,
                "expr": expr,
                "refId": chr(65 + i),
                "instant": True,
                "range": False,
                "format": "table",
            }
            for i, (expr, _, _) in enumerate(columns)
        ],
        "transformations": [
            {"id": "merge", "options": {}},
            {
                "id": "organize",
                "options": {
                    "excludeByName": {"Time": True},
                    "renameByName": {
                        f"Value #{chr(65 + i)}": header
                        for i, (_, header, _) in enumerate(columns)
                    },
                },
            },
        ],
    }


def dump(name, dashboard):
    for p in dashboard["panels"]:
        for t in p.get("targets", []):
            t["expr"] = scoped(t["expr"])
    dashboard["templating"] = {"list": [NODE_VAR]}
    with open(f"{OUT}/{name}", "w", encoding="utf-8") as fh:
        json.dump(dashboard, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    ps = dashboard["panels"]
    print(
        f"{name}: панелей {len([p for p in ps if p['type'] != 'row'])},"
        f" рядов {len([p for p in ps if p['type'] == 'row'])}"
    )


LOSS_STEPS = [
    {"color": "green", "value": None},
    {"color": "yellow", "value": 5},
    {"color": "red", "value": 10},
]
BAD_IF_ANY = [{"color": "green", "value": None}, {"color": "red", "value": 1}]

# =========================================================================
# VPN: трафик и качество
# =========================================================================
panels = []
y = 0

# Per person and transport. A shared office IP maps to one "A, B" username,
# so a row is an address, not necessarily one human.
BY_WHO = "username, inbound"


def sent(w):
    return named(f"rate(vpn_client_tcp_sent_bytes_total[{w}])")


def retr(w):
    return named(f"rate(vpn_client_tcp_retrans_bytes_total[{w}])")


def active(w):
    return f"(sum by ({BY_WHO}) ({sent(w)}) > {ACTIVE_BPS})"


def loss(w):
    return (
        f"100 * sum by ({BY_WHO}) ({retr(w)}) / sum by ({BY_WHO}) ({sent(w)})"
        f" and {active(w)}"
    )


# --- Сводка -------------------------------------------------------------
panels.append(row(100, "Сводка", y))
y += 1
panels += [
    stat(
        1,
        "Пользователей онлайн",
        0,
        y,
        4,
        4,
        [
            (
                "sum(remnawave_node_online_users"
                " * on (node_uuid) group_left remnawave_node_basic_info)",
                "онлайн",
            )
        ],
        desc="По данным панели, со всех нод и всех транспортов, включая Hysteria2.",
    ),
    stat(
        2,
        "Трафик наружу",
        4,
        y,
        4,
        4,
        [(f"sum({vpn_nodes(EGRESS)})", "исходящий")],
        unit="Bps",
        desc="Сумма исходящего трафика всех VPN-нод.",
    ),
    stat(
        3,
        "Худшая доля потерь",
        8,
        y,
        4,
        4,
        [(f"max({loss('10m')})", "потери")],
        unit="percent",
        steps=LOSS_STEPS,
        decimals=1,
        desc=f"Самый пострадавший клиент за 10 минут, среди тех, кому отдаётся больше "
        f"{ACTIVE_BPS // 1024} КиБ/с. Порог алерта — 10 %.",
    ),
    stat(
        4,
        "Повторов SYN в секунду",
        12,
        y,
        4,
        4,
        [
            (
                f"sum({vpn_nodes('rate(node_netstat_TcpExt_TCPSynRetrans[10m])')})",
                "SYN/с",
            )
        ],
        steps=[{"color": "green", "value": None}, {"color": "red", "value": 10}],
        desc="Клиенты не могут установить соединение. Порог алерта — 10/с.",
    ),
    stat(
        5,
        "Сборщиков не работает",
        16,
        y,
        4,
        4,
        [
            (
                f"{nodes_without('xray_up')} + {nodes_without('hy2_collector_up')}",
                "сборщиков",
            )
        ],
        steps=BAD_IF_ANY,
        instant=True,
        desc="Экспорт счётчиков xray и eBPF по Hysteria2 на каждой ноде панели. Нода, которая "
        "перестала присылать метрики совсем, тоже считается. 0 — все живы.",
    ),
    stat(
        7,
        "Алертов горит",
        20,
        y,
        4,
        4,
        [('count(ALERTS{alertstate="firing"}) or vector(0)', "алертов")],
        steps=BAD_IF_ANY,
        instant=True,
    ),
]
y += 4

# --- Кто сейчас ---------------------------------------------------------
panels.append(row(106, "Кто сейчас подключён", y))
y += 1
panels += [
    table(
        6,
        "Клиенты за последние 10 минут",
        0,
        y,
        24,
        8,
        [
            (
                f"sum by ({BY_WHO}) ({sent('10m')}) * 8 and {active('10m')}",
                "Отдача клиенту",
                "bps",
            ),
            (loss("10m"), "Потери", "percent"),
            (
                f"max by ({BY_WHO}) ({named('vpn_client_tcp_rtt_ms')}) and {active('10m')}",
                "RTT",
                "ms",
            ),
        ],
        desc=f"TCP-транспорты, клиенты с отдачей больше {ACTIVE_BPS // 1024} КиБ/с. Hysteria2 — "
        "в разделе ниже. Несколько имён через запятую — общий адрес (офис, NAT), а не "
        "несколько пострадавших. Потери до 5 % у российских провайдеров — фон.",
    ),
]
y += 8

# --- Трафик -------------------------------------------------------------
panels.append(row(101, "Трафик", y))
y += 1
panels += [
    panel(
        10,
        "По транспортам, отдача клиентам",
        0,
        y,
        8,
        8,
        [
            (
                "sum by (tag) ("
                + base_tag(
                    'rate(xray_inbound_traffic_bytes_total{direction="downlink",tag!="REMNAWAVE_API_INBOUND"}[$__rate_interval])'
                )
                + ")",
                "{{tag}}",
            )
        ],
        unit="Bps",
        stack=True,
        desc="Счётчики самого xray, копии инбаундов выделенных нод сложены с общими.",
    ),
    panel(
        12,
        "По нодам, отдача клиентам",
        8,
        y,
        8,
        8,
        [
            (
                'sum by (instance) (rate(xray_inbound_traffic_bytes_total{direction="downlink"}[$__rate_interval]))',
                "{{instance}}",
            )
        ],
        unit="Bps",
        stack=True,
    ),
    panel(
        11,
        "По пользователям",
        16,
        y,
        8,
        8,
        [
            (
                named_user(
                    'sum by (user) (rate(xray_user_traffic_bytes_total{direction="downlink"}[$__rate_interval])) > 0'
                ),
                "{{username}}",
            )
        ],
        unit="Bps",
        stack=True,
        desc="Имя берётся из панели по числовому id (поле email в access.log).",
    ),
]
y += 8

# --- Неделя по пользователям ---------------------------------------------
# Daily buckets answer "was it bad for someone this week" without the per-IP
# noise of the live graphs: one bar per person per day.
panels.append(row(107, "По дням и по людям", y))
y += 1
panels += [
    panel(
        13,
        "Трафик за сутки",
        0,
        y,
        12,
        8,
        [
            (
                named_user(
                    "sum by (user) (increase(xray_user_traffic_bytes_total[1d])) > 1e6"
                ),
                "{{username}}",
            )
        ],
        unit="bytes",
        stack=True,
        bars=True,
        interval="1d",
        calcs=("sum",),
        desc="Отдача и приём вместе, все ноды и транспорты, включая Hysteria2.",
    ),
    panel(
        14,
        "Потери за сутки",
        12,
        y,
        12,
        8,
        [
            (
                f"100 * sum by (username) ({named('increase(vpn_client_tcp_retrans_bytes_total[1d])')})"
                f" / sum by (username) ({named('increase(vpn_client_tcp_sent_bytes_total[1d])')})"
                f" and sum by (username) ({named('increase(vpn_client_tcp_sent_bytes_total[1d])')}) > 5e7",
                "{{username}}",
            )
        ],
        unit="percent",
        bars=True,
        interval="1d",
        calcs=("mean", "max"),
        decimals=1,
        desc="Доля повторно отправленных байтов за сутки, TCP-транспорты, только при отдаче "
        "больше 50 МБ за день. Это главный ответ на «было ли плохо на этой неделе».",
    ),
]
y += 8

# --- Качество -----------------------------------------------------------
panels.append(row(102, "Качество связи по клиентам", y))
y += 1
panels += [
    panel(
        20,
        "Доля потерь",
        0,
        y,
        12,
        8,
        [(loss("$__rate_interval"), "{{username}} · {{inbound}}")],
        unit="percent",
        interval="5m",
        decimals=1,
        desc=f"Повторно отправленные байты к отправленным, по человеку и транспорту, только при "
        f"отдаче больше {ACTIVE_BPS // 1024} КиБ/с. Окно не короче 5 минут.",
    ),
    panel(
        21,
        "RTT",
        12,
        y,
        12,
        8,
        [
            (
                f"max by ({BY_WHO}) ({named('vpn_client_tcp_rtt_ms')}) and {active('$__rate_interval')}",
                "{{username}} · {{inbound}}",
            )
        ],
        unit="ms",
        interval="5m",
        desc="Сглаженный RTT ядра от ноды до клиента, худший сокет. Рост без роста потерь — "
        "очередь на пути.",
    ),
]
y += 8

# --- Hysteria2 ----------------------------------------------------------
panels.append(row(103, "Hysteria2 (eBPF)", y))
y += 1
panels += [
    panel(
        30,
        "Hysteria2 по нодам",
        0,
        y,
        12,
        8,
        [
            (
                "sum by (instance) (rate(hy2_tx_bytes_total[$__rate_interval])) * 8",
                "{{instance}} → отдача",
            ),
            (
                "sum by (instance) (rate(hy2_rx_bytes_total[$__rate_interval])) * 8",
                "{{instance}} ← приём",
            ),
        ],
        unit="bps",
        desc="Для UDP ядро не хранит состояния потока, поэтому данные снимаются пробами eBPF "
        "на udp_queue_rcv_one_skb и udp_send_skb.",
    ),
    panel(
        32,
        "Hysteria2 по людям",
        12,
        y,
        8,
        8,
        [
            (
                f"sum by (username) ({named('rate(hy2_tx_bytes_total[$__rate_interval])')}) * 8 > 0",
                "{{username}}",
            )
        ],
        unit="bps",
        stack=True,
    ),
    stat(
        31,
        "Отброшено датаграмм за период",
        20,
        y,
        4,
        8,
        [("sum(increase(hy2_drops_total[$__range])) or vector(0)", "датаграмм")],
        steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 100}],
        instant=True,
        desc="Причину ядро отдаёт само: фильтр, нет сокета, переполнение очереди.",
    ),
]
y += 8

# --- Восстановление TCP -------------------------------------------------
panels.append(row(104, "Как ядро справляется с потерями", y))
y += 1
panels += [
    panel(
        40,
        "Доля лишних и потерянных повторов",
        0,
        y,
        24,
        8,
        [
            (
                vpn_nodes(
                    "100 * rate(node_tcp_dsack_received_total[1h]) / rate(node_netstat_Tcp_RetransSegs[1h])"
                ),
                "{{instance}} · повтор был лишним",
            ),
            (
                vpn_nodes(
                    "100 * rate(node_tcp_lost_retransmit_total[1h]) / rate(node_netstat_Tcp_RetransSegs[1h])"
                ),
                "{{instance}} · потерялся сам повтор",
            ),
        ],
        unit="percent",
        decimals=1,
        desc="Доля от всех повторов ноды за час. Первая линия — насколько TCP ошибается, "
        "принимая задержку за потерю; вторая — признак тяжёлых потерь на пути.",
    ),
]
y += 8

# --- Из России ----------------------------------------------------------
# roles/vpn_probe on the office testbed: every subscription host, the way a
# user connects, every five minutes. Lanes are hosts, colour is the share of
# requests that got through.
panels.append(row(108, "Из России (проба из офиса)", y))
y += 1
panels += [
    timeline(
        60,
        "Хосты подписки",
        0,
        y,
        16,
        10,
        [("max by (host) (vpn_probe_success_ratio)", "{{host}}")],
        interval="5m",
        desc="Доля запросов, прошедших через хост, по каждому прогону пробы из офиса. "
        "Серый — проба не работала (тестбед выключен). Красная полоса у всех разом при "
        "красном «прямой выход» — лёг офисный канал, а не VPN.",
    ),
    timeline(
        61,
        "Прямой выход и подписка",
        16,
        y,
        8,
        5,
        [
            ("max(vpn_probe_direct_success)", "прямой выход"),
            ("max(vpn_probe_subscription_success)", "подписка"),
        ],
        interval="5m",
    ),
    panel(
        62,
        "Время ответа через хост",
        16,
        y + 5,
        8,
        5,
        [("max by (host) (vpn_probe_latency_seconds)", "{{host}}")],
        unit="s",
        interval="5m",
        calcs=("mean", "max"),
    ),
]
y += 10

# --- Доступность -------------------------------------------------------
# Gatus probes from the control plane in Sweden: TCP connect, ICMP and the
# panel's view of the node. It cannot see a protocol-level failure or the
# Russian path — that is what the probe from the office is for.
panels.append(row(105, "Доступность (SLA)", y))
y += 1
SLA_OK = 'sum by (name) (increase(gatus_results_total{success="true"}[$__range]))'
SLA_ALL = "sum by (name) (increase(gatus_results_total[$__range]))"
panels += [
    stat(
        50,
        "Худшая доступность за период",
        0,
        y,
        6,
        6,
        [(f"min(100 * ({SLA_OK}) / ({SLA_ALL}))", "минимум")],
        unit="percent",
        decimals=2,
        instant=True,
        steps=[
            {"color": "red", "value": None},
            {"color": "yellow", "value": 99.5},
            {"color": "green", "value": 99.9},
        ],
        desc="Самая проблемная проверка gatus за выбранный период. Проверки идут из Швеции и "
        "видят только доступность адреса, а не работу протоколов из России.",
    ),
    timeline(
        51,
        "Проверки по часам",
        6,
        y,
        18,
        6,
        [
            (
                "avg by (name) (avg_over_time(gatus_results_endpoint_success[1h]))",
                "{{name}}",
            )
        ],
        interval="1h",
        desc="Доля успешных проверок за каждый час: зелёный — все, жёлтый — часть, красный — "
        "большинство упало.",
    ),
    panel(
        52,
        "Время отклика проверок",
        0,
        y + 6,
        24,
        7,
        [("gatus_results_duration_seconds", "{{name}}")],
        unit="s",
        desc="Сколько занимает сама проверка. Рост до того, как она начнёт падать, — самый "
        "ранний признак беды.",
    ),
]
y += 13

dump(
    "network/vpn-traffic.json",
    {
        "uid": "vpn-traffic-quality",
        "title": "VPN · трафик и качество",
        "description": "Кто подключён и как ему, трафик по транспортам и людям, недельная картина, "
        "Hysteria2 из eBPF, доступность.",
        "tags": ["vpn", "traffic"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 2,
        "refresh": "1m",
        "time": {"from": "now-7d", "to": "now"},
        "editable": True,
        "panels": panels,
        "templating": {"list": []},
    },
)

# =========================================================================
# VPN: здоровье нод
# =========================================================================
NODE = "* on (node_uuid) group_left (node_name) remnawave_node_basic_info"
panels = []
y = 0
panels += [
    timeline(
        1,
        "Нода на связи с панелью",
        0,
        y,
        12,
        6,
        [(f"remnawave_node_status {NODE}", "{{node_name}}")],
        mappings=[
            {
                "type": "value",
                "options": {
                    "0": {"text": "нет связи", "color": "red"},
                    "1": {"text": "на связи", "color": "green"},
                },
            }
        ],
        desc="Видит ли панель агента ноды. Красный — панель не может раздать ноде конфиг.",
    ),
    panel(
        2,
        "Пользователей онлайн",
        12,
        y,
        12,
        6,
        [(f"remnawave_node_online_users {NODE}", "{{node_name}}")],
        calcs=("lastNotNull", "max"),
    ),
]
y += 6
panels += [
    panel(
        4,
        "Потери UDP на приёме (датаграмм в минуту)",
        0,
        y,
        12,
        7,
        [(vpn_nodes("rate(node_netstat_Udp_RcvbufErrors[5m]) * 60"), "{{instance}}")],
        calcs=("max", "sum"),
        desc="Датаграммы, которые ядро выбросило из-за полного буфера сокета. Бьёт по Hysteria2 и QUIC.",
    ),
    panel(
        5,
        "Доля TCP-ретрансмитов",
        12,
        y,
        12,
        7,
        [
            (
                vpn_nodes(
                    "100 * rate(node_netstat_Tcp_RetransSegs[15m]) / rate(node_netstat_Tcp_OutSegs[15m])"
                    " and rate(node_netstat_Tcp_OutSegs[15m]) > 500"
                ),
                "{{instance}}",
            )
        ],
        unit="percent",
        decimals=1,
        desc="Все TCP-сокеты ноды, когда она отправляет больше 500 сегментов в секунду: на "
        "пустой ноде десяток повторов даёт «20 %» на ровном месте.",
    ),
]
y += 7
panels += [
    panel(
        6,
        "Трафик нод",
        0,
        y,
        12,
        7,
        [
            (
                f"remnawave_node_network_rx_bytes_per_sec {NODE}",
                "{{node_name}} ← приём",
            ),
            (
                f"remnawave_node_network_tx_bytes_per_sec {NODE}",
                "{{node_name}} → отдача",
            ),
        ],
        unit="Bps",
    ),
    panel(
        7,
        "Свободная память нод",
        12,
        y,
        12,
        7,
        [(f"remnawave_node_memory_free_bytes {NODE}", "{{node_name}}")],
        unit="bytes",
        calcs=("lastNotNull", "min"),
    ),
]
y += 7
panels.append(row(100, "Инфраструктура", y))
y += 1
panels += [
    panel(
        8,
        "Дней до истечения сертификатов",
        0,
        y,
        24,
        7,
        [("gatus_results_certificate_expiration_seconds / 86400", "{{name}}")],
        unit="d",
        calcs=("lastNotNull", "min"),
        desc="Let's Encrypt обновляет за 30 дней до конца. Линия ниже 20 — обновление не отработало.",
    ),
]
y += 7

dump(
    "ops/remnawave-health.json",
    {
        "uid": "remnawave-health",
        "title": "Ноды · здоровье",
        "description": "Связь нод с панелью, онлайн, потери на нодах, трафик и память, сертификаты.",
        "tags": ["vpn", "remnawave"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 2,
        "refresh": "1m",
        "time": {"from": "now-7d", "to": "now"},
        "editable": True,
        "panels": panels,
        "templating": {"list": []},
    },
)
