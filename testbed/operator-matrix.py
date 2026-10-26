#!/usr/bin/env python3
"""
Матрица «оператор × протокол»: где именно и какому транспорту плохо.

Сервер настроен одинаково для всех, а жалобы приходят от разных людей и
всегда разные. Разница — в том, через какого оператора человек приходит и
каким транспортом пользуется. Эти данные уже собираются: качество по каждому
клиенту снимается с сокетов, трафик — из счётчиков xray, Hysteria2 — из eBPF.
Не хватало только разреза по операторам.

Адрес превращается в оператора через RIPEstat: своей базы ASN на нодах нет,
а держать её ради десятка клиентов не стоит. Ответы кешируются на диск —
запрос к RIPE занимает секунду, а адреса повторяются.

Запускать с control-plane: нужен доступ к VictoriaMetrics.

    python3 operator-matrix.py [часов_назад]
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict

VM = os.environ.get("VM_URL", "http://172.18.0.16:8428")
CACHE = "/tmp/asn-cache.json"

# Доля потерь считается из счётчиков, а не берётся готовой: см. tcp-quality.py.
QUERIES = {
    "loss": ("100 * rate(vpn_client_tcp_retrans_bytes_total[{w}])"
             " / rate(vpn_client_tcp_sent_bytes_total[{w}])"),
    "sent": "rate(vpn_client_tcp_sent_bytes_total[{w}]) * 8 / 1e6",
    "rtt": "vpn_client_tcp_rtt_ms",
    "inflation": "vpn_client_tcp_rtt_inflation",
    "spurious": ("100 * rate(vpn_client_tcp_spurious_packets_total[{w}])"
                 " / rate(vpn_client_tcp_retrans_packets_total[{w}])"),
    "reordering": "vpn_client_tcp_reordering",
    "volume": "increase(vpn_client_tcp_sent_bytes_total[{w}]) / 1e6",
}

HY2_QUERIES = {
    "hy2_rx": "rate(hy2_rx_packets_total[{w}])",
    "hy2_mbps": "rate(hy2_tx_bytes_total[{w}]) * 8 / 1e6",
    "hy2_drops": "increase(hy2_drops_total[{w}])",
    "volume": "increase(hy2_tx_bytes_total[{w}]) / 1e6",
}

# Порт 443 публичный: на него круглосуточно стучатся сканеры, а в счётчики
# Hysteria2 попадает исходящий DNS самой ноды. И те и другие отличаются от
# клиента объёмом — за половину суток они не набирают и мегабайта.
MIN_VOLUME_MB = 1.0


def load_cache():
    try:
        with open(CACHE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def operator(ip, cache):
    """Кто держит этот адрес. Ответ RIPE кешируется: адреса повторяются."""
    if ip in cache:
        return cache[ip]
    url = f"https://stat.ripe.net/data/prefix-overview/data.json?resource={ip}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read())["data"]
        asns = data.get("asns") or [{}]
        holder = asns[0].get("holder") or "?"
        name = f"AS{asns[0].get('asn', '?')} {holder.split(',')[0][:26]}"
    except (OSError, ValueError, KeyError, IndexError):
        name = "не определился"
    cache[ip] = name
    with open(CACHE, "w") as fh:
        json.dump(cache, fh)
    return name


def query(expr):
    params = urllib.parse.urlencode({"query": expr})
    try:
        with urllib.request.urlopen(f"{VM}/api/v1/query?{params}", timeout=40) as r:
            return json.loads(r.read())["data"]["result"]
    except (OSError, ValueError, KeyError) as exc:
        print(f"  запрос не прошёл: {exc}", file=sys.stderr)
        return []


def main(hours):
    window = f"{hours}h"
    cache = load_cache()
    rows = defaultdict(dict)

    for name, template in QUERIES.items():
        for s in query(template.format(w=window)):
            m = s["metric"]
            key = (m.get("peer", "?"), m.get("inbound", "?"))
            try:
                rows[key][name] = float(s["value"][1])
            except (TypeError, ValueError):
                pass

    for name, template in HY2_QUERIES.items():
        for s in query(template.format(w=window)):
            m = s["metric"]
            key = (m.get("peer", "?"), "hysteria2")
            try:
                rows[key][name] = rows[key].get(name, 0) + float(s["value"][1])
            except (TypeError, ValueError):
                pass

    rows = {k: v for k, v in rows.items() if v.get("volume", 0) >= MIN_VOLUME_MB}

    if not rows:
        print("данных за окно нет")
        return

    by_operator = defaultdict(list)
    for (peer, inbound), vals in rows.items():
        by_operator[operator(peer, cache)].append((peer, inbound, vals))

    print(f"=== окно {window}\n")
    for op in sorted(by_operator):
        print(op)
        for peer, inbound, v in sorted(by_operator[op], key=lambda x: x[1]):
            bits = []
            if v.get("volume"):
                bits.append(f"{v['volume']:7.1f} МБ")
            if "loss" in v:
                bits.append(f"потери {v['loss']:5.2f}%")
            if "sent" in v and v["sent"] > 0:
                bits.append(f"отдача {v['sent']:6.2f} Мбит/с")
            if "hy2_mbps" in v and v["hy2_mbps"] > 0:
                bits.append(f"отдача {v['hy2_mbps']:6.2f} Мбит/с")
            if "rtt" in v:
                bits.append(f"RTT {v['rtt']:5.0f} мс")
            if v.get("inflation"):
                bits.append(f"×{v['inflation']:.1f}")
            if v.get("spurious"):
                bits.append(f"лишних повторов {v['spurious']:4.0f}%")
            if v.get("reordering"):
                bits.append(f"переупоряд. {v['reordering']:.0f}")
            if v.get("hy2_drops"):
                bits.append(f"дропов {v['hy2_drops']:.0f}")
            print(f"   {peer:16} {inbound:18} " + "  ".join(bits))
        print()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
