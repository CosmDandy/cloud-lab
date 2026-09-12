#!/usr/bin/env python3
"""
Turns the bpftrace output for Hysteria2 into node-exporter textfile metrics.

Runs bpftrace as a long-lived child and reads its JSON stream. Restarting it
every scrape would be wrong twice over: attaching probes costs far more than
the sampling itself, and every restart loses whatever accumulated between the
last print and the exit.

bpftrace clears its maps after each print, so the counters here are deltas.
They are accumulated in this process, which makes the exported values proper
monotonic counters — until the service restarts, at which point they reset and
`rate()` handles the discontinuity the same way it does for any exporter.

Idle series are dropped after a while: a client that disconnected would
otherwise keep its row forever, and on port hopping that is a hundred rows per
client.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict

PROGRAM = "/opt/node-metrics/hy2-ebpf.bt"
TARGET = "/var/lib/node-exporter/textfile/hy2-ebpf.prom"
WRITE_EVERY = 15.0
# Через сколько молчания ряд перестаёт экспортироваться. Пять минут — чтобы
# короткий простой клиента не выглядел как его исчезновение.
IDLE_TIMEOUT = 300.0

MAPS = {
    "@rx_pkts": ("hy2_rx_packets_total", ("peer", "port")),
    "@rx_bytes": ("hy2_rx_bytes_total", ("peer", "port")),
    "@tx_pkts": ("hy2_tx_packets_total", ("peer", "port")),
    "@tx_bytes": ("hy2_tx_bytes_total", ("peer", "port")),
    "@drop_in": ("hy2_drops_total", ("peer", "port", "reason")),
    "@drop_out": ("hy2_drops_total", ("peer", "port", "reason")),
    "@queue_drops": ("hy2_queue_drops_total", ("port",)),
}
# Направление проставляется меткой, а не отдельной метрикой: так график
# «сколько теряем в каждую сторону» строится одним запросом.
DIRECTION = {"@drop_in": "inbound", "@drop_out": "outbound"}

totals = defaultdict(float)
last_seen = {}
lock = threading.Lock()
running = True


def consume(line):
    """Одна строка JSON от bpftrace: либо карта, либо служебное событие."""
    try:
        event = json.loads(line)
    except ValueError:
        return
    if event.get("type") != "map":
        return
    now = time.time()
    for map_name, entries in (event.get("data") or {}).items():
        spec = MAPS.get(map_name)
        if not spec or not isinstance(entries, dict):
            continue
        metric, label_names = spec
        for key, value in entries.items():
            parts = [p.strip() for p in str(key).split(",")]
            if len(parts) != len(label_names):
                continue
            labels = dict(zip(label_names, parts))
            if map_name in DIRECTION:
                labels["direction"] = DIRECTION[map_name]
            series = (metric, tuple(sorted(labels.items())))
            with lock:
                totals[series] += float(value)
                last_seen[series] = now


def render():
    now = time.time()
    lines = [
        "# HELP hy2_rx_packets_total UDP datagrams received from a client on a Hysteria2 port",
        "# TYPE hy2_rx_packets_total counter",
        "# HELP hy2_rx_bytes_total Bytes received from a client on a Hysteria2 port",
        "# TYPE hy2_rx_bytes_total counter",
        "# HELP hy2_tx_packets_total UDP datagrams sent to a client from a Hysteria2 port",
        "# TYPE hy2_tx_packets_total counter",
        "# HELP hy2_tx_bytes_total Bytes sent to a client from a Hysteria2 port",
        "# TYPE hy2_tx_bytes_total counter",
        "# HELP hy2_drops_total Datagrams the kernel dropped, by reason and direction",
        "# TYPE hy2_drops_total counter",
        "# HELP hy2_queue_drops_total Datagrams that did not fit the socket receive queue",
        "# TYPE hy2_queue_drops_total counter",
        "# HELP hy2_collector_up Whether the bpftrace program is attached and reporting",
        "# TYPE hy2_collector_up gauge",
    ]
    with lock:
        lines.append(f"hy2_collector_up {1 if running else 0}")
        stale = [s for s, seen in last_seen.items() if now - seen > IDLE_TIMEOUT]
        for s in stale:
            totals.pop(s, None)
            last_seen.pop(s, None)
        for (metric, labels), value in sorted(totals.items()):
            rendered = ",".join(f'{k}="{v}"' for k, v in labels)
            lines.append(f"{metric}{{{rendered}}} {int(value)}")
    return "\n".join(lines) + "\n"


def write_once():
    body = render()
    directory = os.path.dirname(TARGET)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".hy2-ebpf-")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(body)
        os.chmod(tmp, 0o644)
        os.replace(tmp, TARGET)
    except Exception:
        os.unlink(tmp)
        raise


def writer():
    while running:
        time.sleep(WRITE_EVERY)
        try:
            write_once()
        except OSError as exc:
            print(f"write failed: {exc}", file=sys.stderr)


def main():
    global running

    child = subprocess.Popen(
        ["/usr/bin/bpftrace", "-f", "json", PROGRAM],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
    )

    def shutdown(_signum, _frame):
        global running
        running = False
        child.terminate()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    threading.Thread(target=writer, daemon=True).start()
    write_once()

    for line in child.stdout:
        consume(line)

    running = False
    write_once()
    code = child.wait()
    if code not in (0, -signal.SIGTERM):
        print(f"bpftrace exited with {code}: {child.stderr.read()[:500]}", file=sys.stderr)
    return 0 if code in (0, -signal.SIGTERM) else 1


if __name__ == "__main__":
    sys.exit(main())
