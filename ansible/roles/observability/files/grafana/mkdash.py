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
    "node_network_receive_bytes_total",
    "node_network_transmit_bytes_total",
    "node_tcp_dsack_received_total",
    "node_tcp_lost_retransmit_total",
    "node_tcp_retrans_segs_total",
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
    "label": "Node",
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


RETRANS_ENOUGH = "increase(node_tcp_retrans_segs_total[1h]) > 1000"

# The VM's real interfaces: what the hoster sees and bills. Container, bridge
# and tunnel devices would count the same bytes a second time.
IFACE = 'device!~"lo|docker.*|veth.*|br-.*|amn.*|awg.*|wg.*"'
EGRESS = f"rate(node_network_transmit_bytes_total{{{IFACE}}}[5m])"
INGRESS = f"rate(node_network_receive_bytes_total{{{IFACE}}}[5m])"


# The node agent reports the host's main interface counters (/proc/net/dev of
# eth0) to the panel, which exports them. Same bytes as node-exporter, but the
# panel has them from the minute a node is registered — node-exporter on
# sto-03/04 started a day and a half later and the month came out 30 GB short
# of the hoster's figure. Labelled `instance` like the node-exporter series.
RW_NODE = "* on (node_uuid) group_left (node_name) remnawave_node_basic_info"


def iface_bytes(window, offset=""):
    return label_instance(
        f"sum by (node_uuid) (increase(remnawave_node_network_rx_bytes_total[{window}]"
        f"{offset}) + increase(remnawave_node_network_tx_bytes_total[{window}]{offset}))"
        f" {RW_NODE}"
    )


def label_instance(expr):
    return f'label_replace({expr}, "instance", "$1", "node_name", "(.*)")'


HOSTER_LIMIT = 1e12

# Receive series carry this legend suffix; mirrored() draws them below zero.
RX = " · приём"


def mirrored(p, hide_legend=False):
    """Send above zero, receive below it, each in its own stack."""
    props = [{"id": "custom.transform", "value": "negative-Y"}]
    if p["fieldConfig"]["defaults"]["custom"].get("stacking"):
        props.append(
            {"id": "custom.stacking", "value": {"mode": "normal", "group": "B"}}
        )
    if hide_legend:
        props.append(
            {
                "id": "custom.hideFrom",
                "value": {"legend": True, "tooltip": False, "viz": False},
            }
        )
    p["fieldConfig"]["overrides"].append(
        {"matcher": {"id": "byRegexp", "options": f".*{RX}$"}, "properties": props}
    )
    return p


# Bars over the dashboard's own range instead of fixed days: a 6 h window gets
# 5-minute buckets, a week about 2-hour ones. Grafana stamps a bar at the start
# of its bucket and increase[] looks back, so the window is turned forward.
BUCKET = "[$__interval] offset -$__interval"
BUCKETS = 72


def bucketed(p):
    p["maxDataPoints"] = BUCKETS
    return p


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
# Six columns, a pair of related tiles in each: what to compare sits one
# above the other.
today = stat(
    16,
    "Трафик за сегодня",
    20,
    y,
    4,
    3,
    [(f"sum({iface_bytes('$__range')})", "сегодня")],
    unit="decbytes",
    instant=True,
    desc="Все VPN-ноды, приём и отдача на интерфейсах, с полуночи по времени браузера.",
)
today["timeFrom"] = "now/d"
month_share = stat(
    17,
    "Худшая нода, % лимита месяца",
    20,
    y + 3,
    4,
    3,
    [(f"100 * max({iface_bytes('$__range')}) / {HOSTER_LIMIT:.0f}", "лимит")],
    unit="percent",
    decimals=0,
    steps=[
        {"color": "green", "value": None},
        {"color": "yellow", "value": 80},
        {"color": "red", "value": 100},
    ],
    instant=True,
    desc="Сколько от 1 ТБ хостера израсходовала с начала месяца самая загруженная нода.",
)
month_share["timeFrom"] = "now/M"
panels += [
    stat(
        1,
        "Пользователей онлайн",
        0,
        y,
        4,
        6,
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
        3,
        [(f"sum({vpn_nodes(EGRESS)})", "исходящий")],
        unit="Bps",
        desc="Сумма исходящего трафика всех VPN-нод на интерфейсах.",
    ),
    stat(
        8,
        "Трафик внутрь",
        4,
        y + 3,
        4,
        3,
        [(f"sum({vpn_nodes(INGRESS)})", "входящий")],
        unit="Bps",
        desc="Сумма входящего трафика всех VPN-нод на интерфейсах.",
    ),
    stat(
        3,
        "Худшая доля потерь, TCP",
        8,
        y,
        4,
        3,
        [(f"max({loss('10m')})", "потери")],
        unit="percent",
        steps=LOSS_STEPS,
        decimals=1,
        desc=f"Самый пострадавший клиент за 10 минут, среди тех, кому отдаётся больше "
        f"{ACTIVE_BPS // 1024} КиБ/с. Порог алерта — 10 %.",
    ),
    stat(
        9,
        "UDP сброшено нодами, в минуту",
        8,
        y + 3,
        4,
        3,
        [
            (
                "((sum(rate(hy2_drops_total[10m])) or vector(0))"
                f" + (sum({vpn_nodes('rate(node_netstat_Udp_RcvbufErrors[10m])')})"
                " or vector(0))) * 60",
                "датаграмм",
            )
        ],
        steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 100}],
        desc="Ближайшее к «потерям» для Hysteria2, что видно с ноды: датаграммы, которые "
        "выбросило само ядро. Потери по пути не видны — QUIC их шифрует.",
    ),
    stat(
        4,
        "Повторов SYN в секунду",
        12,
        y,
        4,
        3,
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
        15,
        "Хостов пропало из России",
        12,
        y + 3,
        4,
        3,
        [
            (
                "count(max_over_time(vpn_probe_success_ratio[12m]) == 0"
                " and avg_over_time(vpn_probe_success_ratio[1d] offset 15m) > 0.5"
                " and on (instance) last_over_time(vpn_probe_direct_success[12m]) == 1)"
                " or vector(0)",
                "хостов",
            )
        ],
        steps=BAD_IF_ANY,
        instant=True,
        desc="Хосты подписки, которые из офиса работали, а теперь не проходят — то же "
        "условие, что у алерта ProtocolDeadFromRussia. Хосты, которые из офиса не "
        "проходят постоянно, сюда не попадают.",
    ),
    stat(
        7,
        "Алертов горит",
        16,
        y,
        4,
        3,
        [('count(ALERTS{alertstate="firing"}) or vector(0)', "алертов")],
        steps=BAD_IF_ANY,
        instant=True,
    ),
    stat(
        5,
        "Сборщиков не работает",
        16,
        y + 3,
        4,
        3,
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
    today,
    month_share,
]
y += 6

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


# Traffic comes from the panel, not from xray's counters on the node: the panel
# reads those with reset every few seconds, so the node-side exporter sees
# only what piled up since the last reset — about a third of the real volume.
# The panel's totals update every two minutes, hence the 5m floor on these
# panels. "download" is towards the client (what we send), "upload" is what
# the client sends us.
RW_INBOUND = {
    "downlink": "remnawave_node_inbound_download_bytes",
    "uplink": "remnawave_node_inbound_upload_bytes",
}
TRAFFIC_STEP = "5m"


def by_tag(direction):
    return (
        "sum by (tag) ("
        + base_tag(
            f'rate({RW_INBOUND[direction]}{{tag!="REMNAWAVE_API_INBOUND"}}'
            f"[$__rate_interval]) {RW_NODE}"
        )
        + ")"
    )


def by_node(direction):
    return (
        f"sum by (node_name) (rate({RW_INBOUND[direction]}[$__rate_interval])"
        f" {RW_NODE})"
    )


# Per user the panel keeps only one total, both directions together.
def by_user():
    return named_user(
        "sum by (user) (rate(vpn_user_traffic_bytes_total[$__rate_interval])) > 0"
    )


MIRROR_NOTE = "Отдача клиентам — вверх от нуля, приём от клиентов — вниз."
panels += [
    mirrored(
        panel(
            10,
            "По транспортам",
            0,
            y,
            8,
            8,
            [
                (by_tag("downlink"), "{{tag}}"),
                (by_tag("uplink"), "{{tag}}" + RX),
            ],
            unit="Bps",
            stack=True,
            interval=TRAFFIC_STEP,
            desc=f"{MIRROR_NOTE} Счётчики панели по инбаундам, копии инбаундов "
            "выделенных нод сложены с общими. Полезная нагрузка без заголовков: на "
            "интерфейсе ноды байтов примерно вдвое больше — каждый байт входит из "
            "интернета и выходит к клиенту.",
        )
    ),
    mirrored(
        panel(
            12,
            "По нодам",
            8,
            y,
            8,
            8,
            [
                (by_node("downlink"), "{{node_name}}"),
                (by_node("uplink"), "{{node_name}}" + RX),
            ],
            unit="Bps",
            stack=True,
            interval=TRAFFIC_STEP,
            desc=f"{MIRROR_NOTE} Счётчики панели, как в «По транспортам».",
        )
    ),
    panel(
        11,
        "По пользователям",
        16,
        y,
        8,
        8,
        [(by_user(), "{{username}}")],
        unit="Bps",
        stack=True,
        interval=TRAFFIC_STEP,
        desc="Отдача и приём вместе: панель хранит по человеку только общий счётчик. "
        "Все ноды сразу, фильтр Node сюда не действует.",
    ),
]
y += 8

# --- По людям за интервал -------------------------------------------------
# Bars per person per bucket answer "was it bad for someone" without the
# per-IP noise of the live graphs; the bucket follows the chosen range.
panels.append(row(107, "По людям за интервал", y))
y += 1


def user_bytes():
    return named_user(
        f"sum by (user) (increase(vpn_user_traffic_bytes_total{BUCKET})) > 1e6"
    )


def client_bytes(metric):
    return f"sum by (username) ({named(f'increase({metric}{BUCKET})')})"


# A share needs volume behind it: on average 2 KiB/s over the bucket, i.e.
# about 180 MB a day or 600 KB in 5 minutes.
LOSS_FLOOR = "2048 * $__interval_ms / 1000"
BUCKET_NOTE = (
    "Ширина столбца зависит от выбранного периода: на 6 часах около 5 минут, на неделе "
    "около 2 часов. Столбец подписан началом своего интервала."
)
panels += [
    bucketed(
        panel(
            13,
            "Трафик по людям",
            0,
            y,
            12,
            8,
            [(user_bytes(), "{{username}}")],
            unit="bytes",
            stack=True,
            bars=True,
            interval="5m",
            calcs=("sum",),
            desc="Отдача и приём вместе, все ноды и транспорты, включая Hysteria2; "
            f"счётчик панели. {BUCKET_NOTE} В легенде сумма за период.",
        )
    ),
    bucketed(
        panel(
            14,
            "Потери по людям",
            12,
            y,
            12,
            8,
            [
                (
                    f"100 * {client_bytes('vpn_client_tcp_retrans_bytes_total')}"
                    f" / {client_bytes('vpn_client_tcp_sent_bytes_total')}"
                    f" and {client_bytes('vpn_client_tcp_sent_bytes_total')}"
                    f" > {LOSS_FLOOR}",
                    "{{username}}",
                )
            ],
            unit="percent",
            bars=True,
            interval="5m",
            calcs=("mean", "max"),
            decimals=1,
            desc="Доля повторно отправленных байтов за интервал, TCP-транспорты, только "
            f"при отдаче в среднем больше 2 КиБ/с. {BUCKET_NOTE}",
        )
    ),
]
y += 8

# --- Качество -----------------------------------------------------------
panels.append(row(102, "TCP-транспорты (Vision, gRPC, XHTTP): качество по клиентам", y))
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
panels.append(row(103, "Hysteria2 (UDP, eBPF)", y))
y += 1


def hy2_by_user(metric):
    return f"sum by (username) ({named(f'rate({metric}[$__rate_interval])')}) * 8 > 0"


panels += [
    mirrored(
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
                    "{{instance}}",
                ),
                (
                    "sum by (instance) (rate(hy2_rx_bytes_total[$__rate_interval])) * 8",
                    "{{instance}}" + RX,
                ),
            ],
            unit="bps",
            desc=f"{MIRROR_NOTE} Для UDP ядро не хранит состояния потока, поэтому данные "
            "снимаются пробами eBPF на udp_queue_rcv_one_skb и udp_send_skb.",
        )
    ),
    mirrored(
        panel(
            32,
            "Hysteria2 по людям",
            12,
            y,
            8,
            8,
            [
                (hy2_by_user("hy2_tx_bytes_total"), "{{username}}"),
                (hy2_by_user("hy2_rx_bytes_total"), "{{username}}" + RX),
            ],
            unit="bps",
            stack=True,
            desc=MIRROR_NOTE,
        ),
        hide_legend=True,
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
            # The denominator comes from the same nstat read as the numerator
            # (nstat-extra.py), not from node-exporter: see the note there.
            # The kernel marks a retransmit lost or reported as duplicate up
            # to an RTO after sending it, so with a handful of retransmits
            # per hour the share still jumps past 100 %; below 1000 it is
            # noise and is not drawn.
            (
                vpn_nodes(
                    "100 * rate(node_tcp_dsack_received_total[1h])"
                    " / rate(node_tcp_retrans_segs_total[1h])"
                    f" and {RETRANS_ENOUGH}"
                ),
                "{{instance}} · повтор был лишним",
            ),
            (
                vpn_nodes(
                    "100 * rate(node_tcp_lost_retransmit_total[1h])"
                    " / rate(node_tcp_retrans_segs_total[1h])"
                    f" and {RETRANS_ENOUGH}"
                ),
                "{{instance}} · потерялся сам повтор",
            ),
        ],
        unit="percent",
        decimals=1,
        desc="Доля от всех повторов ноды за час. Первая линия — насколько TCP ошибается, "
        "принимая задержку за потерю; вторая — признак тяжёлых потерь на пути. "
        "Рисуется, только когда повторов за час больше тысячи: на меньшем числе "
        "доля скачет и ничего не значит. Первая линия выше 100 % — клиенты получили "
        "больше дубликатов, чем мы повторили: пакеты дублирует сам путь (переупорядочивание, "
        "сеть провайдера), а не наш TCP. Вреда нет, клиент выбрасывает копии.",
    ),
]
y += 8

# --- Из России ----------------------------------------------------------
# roles/vpn_probe on the office testbed: every subscription host, the way a
# user connects, every five minutes. 24 hosts in one timeline were unreadable,
# so the same data is cut three ways: now as a transport x node grid, and over
# time per node and per transport.
panels.append(row(108, "Из России (проба из офиса)", y))
y += 1
# The timer is OnUnitInactiveSec=5min, so runs land every 5 min plus the
# run itself: a 5m window is regularly empty and the lane breaks. 10m always
# holds a run; a gap then means the probe really did not run.
PROBE_STEP = "10m"
PROBE_OK = "avg_over_time(vpn_probe_success_ratio[$__interval])"
probe_now = {
    "id": 64,
    "type": "table",
    "title": "Сейчас: транспорт × нода",
    "description": "Доля запросов, прошедших через хост, по последнему прогону пробы. "
    "Пусто — такого хоста в подписке нет.",
    "datasource": DS,
    "gridPos": {"x": 0, "y": y, "w": 8, "h": 9},
    "fieldConfig": {
        "defaults": {
            "unit": "percentunit",
            "decimals": 0,
            "custom": {"align": "center", "cellOptions": {"type": "color-background"}},
            "color": {"mode": "thresholds"},
            "thresholds": {
                "mode": "absolute",
                "steps": [
                    {"color": "red", "value": None},
                    {"color": "yellow", "value": 0.5},
                    {"color": "green", "value": 0.99},
                ],
            },
        },
        "overrides": [],
    },
    "options": {"showHeader": True, "cellHeight": "sm"},
    "targets": [
        {
            "datasource": DS,
            "expr": "max by (transport, node) "
            "(last_over_time(vpn_probe_success_ratio[15m]))",
            "refId": "A",
            "instant": True,
            "range": False,
            "format": "table",
        }
    ],
    # The backend answers one frame per series with node and transport as
    # labels; they become columns of one table before the matrix is built.
    "transformations": [
        {"id": "labelsToFields", "options": {"mode": "columns"}},
        {"id": "merge", "options": {}},
        {
            "id": "groupingToMatrix",
            "options": {
                "columnField": "node",
                "rowField": "transport",
                "valueField": "Value",
            },
        },
    ],
}
panels += [
    probe_now,
    timeline(
        60,
        "По нодам",
        8,
        y,
        16,
        4,
        [(f"avg by (node) ({PROBE_OK})", "{{node}}")],
        interval=PROBE_STEP,
        desc="Средняя доля прошедших запросов по всем транспортам ноды. Жёлтый у ноды, "
        "на которой из офиса не проходят Vision и gRPC, — постоянный фон, а не авария. "
        "Серый — проба не работала (тестбед выключен).",
    ),
    timeline(
        63,
        "По транспортам",
        8,
        y + 4,
        16,
        5,
        [(f"avg by (transport) ({PROBE_OK})", "{{transport}}")],
        interval=PROBE_STEP,
        desc="Средняя доля прошедших запросов по всем нодам. Красное у всех разом при "
        "красном «прямой выход» — лёг офисный канал, а не VPN.",
    ),
    timeline(
        61,
        "Прямой выход и подписка",
        0,
        y + 9,
        8,
        5,
        [
            (
                "max(min_over_time(vpn_probe_direct_success[$__interval]))",
                "прямой выход",
            ),
            (
                "max(min_over_time(vpn_probe_subscription_success[$__interval]))",
                "подписка",
            ),
        ],
        interval=PROBE_STEP,
    ),
    panel(
        62,
        "Время ответа через ноду",
        8,
        y + 9,
        16,
        5,
        [
            (
                "avg by (node) (avg_over_time(vpn_probe_latency_seconds[$__interval]))",
                "{{node}}",
            )
        ],
        unit="s",
        interval=PROBE_STEP,
        calcs=("mean", "max"),
        desc="Среднее по транспортам, только прошедшие запросы.",
    ),
]
y += 14

# --- Доступность -------------------------------------------------------
# Gatus probes from the control plane in Sweden: TCP connect, ICMP and the
# panel's view of the node. It cannot see a protocol-level failure or the
# Russian path — that is what the probe from the office is for. Only the VPN
# checks live here; the rest of the services sit on Nodes · health.
panels.append(row(105, "Доступность (SLA)", y))
y += 1
VPN_CHECKS = 'group=~"vpn|vpn nodes"'
SLA_OK = (
    f'sum by (name) (increase(gatus_results_total{{{VPN_CHECKS}, success="true"}}'
    "[$__range]))"
)
SLA_ALL = f"sum by (name) (increase(gatus_results_total{{{VPN_CHECKS}}}[$__range]))"
GATUS_OK = "avg_over_time(gatus_results_endpoint_success{%s}[$__interval])"
NODE_CHECKS_OK = GATUS_OK % 'group="vpn nodes"'
PANEL_CHECKS_OK = GATUS_OK % 'group="vpn"'


def per_node(expr):
    """hhh-sto-03-icmp, -tcp and -panel become one node=hhh-sto-03."""
    return f'label_replace({expr}, "node", "$1", "name", "(hhh-[a-z]+-[0-9]+)-.*")'


panels += [
    stat(
        50,
        "Худшая доступность за период",
        0,
        y,
        4,
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
        desc="Самая проблемная VPN-проверка gatus за выбранный период. Проверки идут из "
        "Швеции и видят только доступность адреса, а не работу протоколов из России.",
    ),
    timeline(
        51,
        "Проверки",
        4,
        y,
        20,
        6,
        [
            (f"min by (node) ({per_node(NODE_CHECKS_OK)})", "{{node}}"),
            (f"avg by (name) ({PANEL_CHECKS_OK})", "{{name}}"),
        ],
        interval="5m",
        desc="Нода — худшее из трёх её проверок: ping, TCP-подключение и связь с "
        "панелью. Зелёный — все прошли, жёлтый — часть, красный — большинство упало.",
    ),
    panel(
        52,
        "TCP-подключение к нодам",
        0,
        y + 6,
        12,
        7,
        [
            (
                per_node(
                    'max by (name) (gatus_results_duration_seconds{group="vpn nodes",'
                    ' type="TCP"}) and on (name) (gatus_results_endpoint_success == 1)'
                ),
                "{{node}}",
            )
        ],
        unit="s",
        calcs=("mean", "max"),
        desc="Время установки TCP-соединения из Швеции, только удачные проверки: "
        "неудачная рисовалась бы таймаутом в 10 с и сплющивала график.",
    ),
    panel(
        53,
        "Ответ панели и подписки",
        12,
        y + 6,
        12,
        7,
        [
            (
                'max by (name) (gatus_results_duration_seconds{group="vpn"})'
                " and on (name) (gatus_results_endpoint_success == 1)",
                "{{name}}",
            )
        ],
        unit="s",
        calcs=("mean", "max"),
        desc="Полный HTTP-запрос из Швеции, только удачные проверки. Рост до того, как "
        "проверка начнёт падать, — самый ранний признак беды.",
    ),
]
y += 13

dump(
    "network/vpn-traffic.json",
    {
        "uid": "vpn-traffic-quality",
        "title": "VPN · traffic & quality",
        "description": "Сводка, трафик по транспортам, нодам и людям, качество TCP и "
        "Hysteria2, проба из России, доступность VPN.",
        "tags": ["vpn", "traffic"],
        "timezone": "browser",
        "graphTooltip": 1,
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
    mirrored(
        panel(
            6,
            "Трафик нод",
            0,
            y,
            12,
            7,
            [
                (f"remnawave_node_network_tx_bytes_per_sec {NODE}", "{{node_name}}"),
                (
                    f"remnawave_node_network_rx_bytes_per_sec {NODE}",
                    "{{node_name}}" + RX,
                ),
            ],
            unit="Bps",
            desc="Отдача — вверх от нуля, приём — вниз.",
        )
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

# HostHatch bills 1 TB a month per node and counts both directions on the
# VM's interface, so this is rx + tx on the real interfaces, not the panel's
# xray counter (which sees only the proxied payload, once). The panel's
# "relative time" now/M makes $__range the month so far in the browser's
# timezone; the hoster's month may start a few hours apart.
month = stat(
    9,
    "Расход трафика с начала месяца (интерфейс, приём + отдача)",
    0,
    y,
    12,
    7,
    [(iface_bytes("$__range"), "{{instance}}")],
    unit="decbytes",
    steps=[
        {"color": "green", "value": None},
        {"color": "yellow", "value": 0.8 * HOSTER_LIMIT},
        {"color": "red", "value": HOSTER_LIMIT},
    ],
    instant=True,
    desc="Столько насчитает хостер: каждый байт на интерфейсе ВМ, в обе стороны. "
    "Лимит HostHatch — 1 ТБ в месяц на ноду: жёлтый с 800 ГБ, красный с 1 ТБ. "
    "Счётчик панели remnawave меньше: он видит только трафик xray.",
)
month["type"] = "bargauge"
month["timeFrom"] = "now/M"
month["fieldConfig"]["defaults"].update({"min": 0, "max": HOSTER_LIMIT})
month["options"] = {
    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
    "orientation": "horizontal",
    "displayMode": "gradient",
    "showUnfilled": True,
}
# Grafana aligns the 1d points to midnight in the dashboard timezone, and
# increase[1d] at a point looks back: the bar stamped 23.10 would be the whole
# of 22.10. offset -1d turns the window forward so each bar is its own day and
# today's bar is today so far.
daily = panel(
    10,
    "Расход трафика по дням (интерфейс, приём + отдача)",
    12,
    y,
    12,
    7,
    [(iface_bytes("1d", " offset -1d"), "{{instance}}")],
    unit="decbytes",
    bars=True,
    stack=True,
    interval="1d",
    calcs=("mean", "max", "sum"),
    desc="Календарные сутки в часовом поясе браузера; последний столбец — "
    "сегодня с полуночи. Ноды сложены друг на друга: высота столбца — весь "
    "трафик VPN за сутки, цвет — доля каждой ноды. Лимит считается по ноде: "
    "чтобы уложиться в 1 ТБ за 30 дней, одной ноде нужно в среднем не больше "
    "33 ГБ в сутки.",
)
daily["timeFrom"] = "30d"
panels += [month, daily]
y += 7
panels.append(row(100, "Инфраструктура", y))
y += 1
panels += [
    timeline(
        11,
        "Сервисы (gatus из Швеции)",
        0,
        y,
        12,
        7,
        [
            (
                "avg by (name) (avg_over_time(gatus_results_endpoint_success"
                '{group!~"vpn.*"}[$__interval]))',
                "{{name}}",
            )
        ],
        interval="5m",
        desc="Проверки всего, кроме VPN: VPN-проверки — на дашборде VPN · traffic & "
        "quality. Зелёный — все прошли, жёлтый — часть, красный — большинство упало.",
    ),
    panel(
        8,
        "Дней до истечения сертификатов",
        12,
        y,
        12,
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
        "title": "Nodes · health",
        "description": "Связь нод с панелью, онлайн, потери на нодах, трафик и память, "
        "сервисы и сертификаты.",
        "tags": ["vpn", "remnawave"],
        "timezone": "browser",
        "graphTooltip": 1,
        "schemaVersion": 39,
        "version": 2,
        "refresh": "1m",
        "time": {"from": "now-7d", "to": "now"},
        "editable": True,
        "panels": panels,
        "templating": {"list": []},
    },
)
