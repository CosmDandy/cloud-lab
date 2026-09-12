#!/usr/bin/env python3
"""
Xray's own counters as a node-exporter textfile.

Xray exposes them at /debug/vars in Go's expvar format, which nothing in the
stack can scrape — hence this converter. What it adds over the panel: traffic
split by user *and* by inbound, sampled every 30 seconds instead of whatever
the panel happens to persist, so a transport going quiet is visible as it
happens rather than in yesterday's totals.

The user key is the panel's numeric user id — the same value that appears as
`email: N` in access.log. Names stay in the panel on purpose: the node has no
business holding them.
"""

import json
import os
import sys
import tempfile
import urllib.request

ENDPOINT = "http://127.0.0.1:9101/debug/vars"


def fetch():
    try:
        with urllib.request.urlopen(ENDPOINT, timeout=10) as r:
            return json.loads(r.read())
    except (OSError, ValueError) as exc:
        print(f"xray stats unavailable: {exc}", file=sys.stderr)
        return None


def render(data):
    lines = [
        "# HELP xray_inbound_traffic_bytes_total Bytes carried by an inbound since xray started",
        "# TYPE xray_inbound_traffic_bytes_total counter",
        "# HELP xray_outbound_traffic_bytes_total Bytes carried by an outbound since xray started",
        "# TYPE xray_outbound_traffic_bytes_total counter",
        "# HELP xray_user_traffic_bytes_total Bytes carried for one user since xray started",
        "# TYPE xray_user_traffic_bytes_total counter",
        "# HELP xray_up Whether xray answered its own stats endpoint",
        "# TYPE xray_up gauge",
    ]
    if data is None:
        lines.append("xray_up 0")
        return "\n".join(lines) + "\n"

    lines.append("xray_up 1")
    stats = data.get("stats") or {}
    for section, metric, label in (
        ("inbound", "xray_inbound_traffic_bytes_total", "tag"),
        ("outbound", "xray_outbound_traffic_bytes_total", "tag"),
        ("user", "xray_user_traffic_bytes_total", "user"),
    ):
        for name, counters in (stats.get(section) or {}).items():
            for direction in ("uplink", "downlink"):
                value = counters.get(direction)
                if value is None:
                    continue
                lines.append(f'{metric}{{{label}="{name}",direction="{direction}"}} {int(value)}')

    # Память процесса: при утечке в ядре она видна здесь задолго до того, как
    # ноду начнёт убивать OOM, а cgroup-метрики покажут только общий итог.
    mem = data.get("memstats") or {}
    if "Alloc" in mem:
        lines += [
            "# HELP xray_memory_alloc_bytes Heap currently allocated by xray",
            "# TYPE xray_memory_alloc_bytes gauge",
            f"xray_memory_alloc_bytes {int(mem['Alloc'])}",
        ]
    if "NumGC" in mem:
        lines += [
            "# HELP xray_gc_cycles_total Completed garbage collection cycles",
            "# TYPE xray_gc_cycles_total counter",
            f"xray_gc_cycles_total {int(mem['NumGC'])}",
        ]
    return "\n".join(lines) + "\n"


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "/var/lib/node-exporter/textfile/xray-stats.prom"
    body = render(fetch())

    directory = os.path.dirname(target)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".xray-stats-")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(body)
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    except Exception:
        os.unlink(tmp)
        raise


if __name__ == "__main__":
    main()
