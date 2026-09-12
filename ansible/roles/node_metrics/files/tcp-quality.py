#!/usr/bin/env python3
"""
Quality of every client TCP connection, as a node-exporter textfile.

Node-level retransmit ratio answers "something is wrong somewhere". This answers
"this client on this inbound is losing 9% right now" — which is the difference
between a graph and an actionable one. The kernel already tracks it per socket;
`ss -ti` just exposes what is there.

**Counters, not ratios.** The obvious implementation — export
bytes_retrans/bytes_sent straight off the socket — was tried first and is wrong.
Those fields are cumulative over the socket's whole life, so the exported value
drifts downward as clean traffic dilutes old losses, then jumps when the client
opens a fresh socket. Alerting on that produces a sawtooth across the threshold
and no information: observed drifting 10.5 → 8.4 → 6.2 → 4.6 while nothing on
the path had changed.

So the per-socket deltas are accumulated here into monotonic counters keyed by
(peer, inbound), and the ratio is left to PromQL, where `rate()` over a window
says what is happening *now*:

    rate(vpn_client_tcp_retrans_bytes_total[10m])
      / rate(vpn_client_tcp_sent_bytes_total[10m])

Sockets come and go; a socket seen for the first time contributes its full
counters, since it was born between two samples. The previous sample is kept on
disk because the collector runs as a timer and exits between runs — losing it
would reset every counter every 30 seconds.

RTT and reordering stay gauges: they describe a state, not an accumulation.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict

# Inbound ports as configured in the panel's config profile. A port missing here
# is simply not reported — node-to-internet sockets are not what we measure.
INBOUNDS = {
    443: "xhttp-stream-443",
    2444: "xhttp-stream",
    2446: "xhttp-packet",
    2054: "vision",
    2084: "grpc",
}

MAX_SERIES = 50
STATE_PATH = "/var/lib/node-metrics/tcp-quality.state"

SOCKET_HEAD = re.compile(
    r"\[?(?:::ffff:)?([\d.]+)\]?:(\d+)\s+\[?(?:::ffff:)?([\d.]+)\]?:(\d+)"
)


def field(pattern, line, default=0.0):
    m = re.search(pattern, line)
    return float(m.group(1)) if m else default


def load_state():
    try:
        with open(STATE_PATH) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"sockets": {}, "totals": {}}


def save_state(state):
    directory = os.path.dirname(STATE_PATH)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tcp-quality-state-")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(state, fh)
        os.replace(tmp, STATE_PATH)
    except Exception:
        os.unlink(tmp)
        raise


def collect():
    """Per-socket sample: current cumulative counters plus live gauges."""
    try:
        out = subprocess.run(
            ["ss", "-tin", "state", "established"],
            capture_output=True, text=True, timeout=20, check=False,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"ss failed: {exc}", file=sys.stderr)
        return {}

    sockets = {}
    key = None
    for line in out:
        head = SOCKET_HEAD.search(line)
        if head and "bytes_sent" not in line:
            port = int(head.group(2))
            if port in INBOUNDS:
                # Local and remote port together identify the connection; the
                # pair is reused rarely enough that a stale match would have to
                # be deliberate.
                key = (head.group(3), INBOUNDS[port], head.group(4))
            else:
                key = None
            continue
        if key is None or "bytes_sent" not in line:
            continue
        sockets["|".join(key)] = {
            "sent": field(r"\bbytes_sent:(\d+)", line),
            "retrans": field(r"\bbytes_retrans:(\d+)", line),
            "dsack": field(r"\bdsack_dups:(\d+)", line),
            "retrans_pkts": field(r"\bretrans:\d+/(\d+)", line),
            "rtt": field(r"\brtt:([\d.]+)", line),
            "minrtt": field(r"\bminrtt:([\d.]+)", line),
            "reordering": field(r"\breordering:(\d+)", line),
        }
        key = None
    return sockets


def accumulate(sockets, state):
    """Fold per-socket growth into counters keyed by (peer, inbound)."""
    previous = state.get("sockets", {})
    totals = defaultdict(float, state.get("totals", {}))

    for sock_key, now in sockets.items():
        peer, inbound, _rport = sock_key.split("|")
        was = previous.get(sock_key)
        for field_name in ("sent", "retrans", "dsack", "retrans_pkts"):
            current = now[field_name]
            # A counter that went backwards means the port was reused by a new
            # connection: treat the whole current value as growth.
            grew = current - was[field_name] if was and current >= was[field_name] else current
            totals[f"{peer}|{inbound}|{field_name}"] += grew

    state["sockets"] = sockets
    state["totals"] = dict(totals)
    return totals


def gauges(sockets):
    """Live state per (peer, inbound): worst RTT inflation, sockets, reordering."""
    live = defaultdict(lambda: {"sockets": 0, "rtt": 0.0, "rtt_n": 0,
                                "minrtt": 0.0, "reordering": 0.0})
    for sock_key, s in sockets.items():
        peer, inbound, _ = sock_key.split("|")
        row = live[(peer, inbound)]
        row["sockets"] += 1
        if s["rtt"]:
            row["rtt"] += s["rtt"]
            row["rtt_n"] += 1
        if s["minrtt"]:
            row["minrtt"] = min(row["minrtt"], s["minrtt"]) if row["minrtt"] else s["minrtt"]
        row["reordering"] = max(row["reordering"], s["reordering"])
    return live


def render(totals, live):
    lines = [
        "# HELP vpn_client_tcp_sent_bytes_total Bytes sent to a client, accumulated across sockets",
        "# TYPE vpn_client_tcp_sent_bytes_total counter",
        "# HELP vpn_client_tcp_retrans_bytes_total Bytes retransmitted to a client",
        "# TYPE vpn_client_tcp_retrans_bytes_total counter",
        "# HELP vpn_client_tcp_retrans_packets_total Segments retransmitted to a client",
        "# TYPE vpn_client_tcp_retrans_packets_total counter",
        "# HELP vpn_client_tcp_spurious_packets_total Retransmits the peer reported as unnecessary",
        "# TYPE vpn_client_tcp_spurious_packets_total counter",
        "# HELP vpn_client_tcp_sockets Established sockets right now",
        "# TYPE vpn_client_tcp_sockets gauge",
        "# HELP vpn_client_tcp_rtt_ms Mean smoothed RTT across the client's sockets",
        "# TYPE vpn_client_tcp_rtt_ms gauge",
        "# HELP vpn_client_tcp_rtt_inflation Current RTT divided by the path minimum",
        "# TYPE vpn_client_tcp_rtt_inflation gauge",
        "# HELP vpn_client_tcp_reordering Kernel reordering estimate, 3 is the default",
        "# TYPE vpn_client_tcp_reordering gauge",
    ]

    by_pair = defaultdict(dict)
    for key, value in totals.items():
        peer, inbound, field_name = key.split("|")
        by_pair[(peer, inbound)][field_name] = value

    ranked = sorted(by_pair.items(), key=lambda kv: -kv[1].get("sent", 0))[:MAX_SERIES]
    for (peer, inbound), counters in ranked:
        tags = f'peer="{peer}",inbound="{inbound}"'
        lines += [
            f"vpn_client_tcp_sent_bytes_total{{{tags}}} {int(counters.get('sent', 0))}",
            f"vpn_client_tcp_retrans_bytes_total{{{tags}}} {int(counters.get('retrans', 0))}",
            f"vpn_client_tcp_retrans_packets_total{{{tags}}} {int(counters.get('retrans_pkts', 0))}",
            f"vpn_client_tcp_spurious_packets_total{{{tags}}} {int(counters.get('dsack', 0))}",
        ]
        row = live.get((peer, inbound))
        if not row:
            continue
        rtt = row["rtt"] / row["rtt_n"] if row["rtt_n"] else 0
        inflation = rtt / row["minrtt"] if row["minrtt"] else 0
        lines += [
            f"vpn_client_tcp_sockets{{{tags}}} {row['sockets']}",
            f"vpn_client_tcp_rtt_ms{{{tags}}} {rtt:.3f}",
            f"vpn_client_tcp_rtt_inflation{{{tags}}} {inflation:.3f}",
            f"vpn_client_tcp_reordering{{{tags}}} {int(row['reordering'])}",
        ]
    lines.append(f"vpn_client_tcp_series_total {len(ranked)}")
    return "\n".join(lines) + "\n"


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "/var/lib/node-exporter/textfile/tcp-quality.prom"

    state = load_state()
    sockets = collect()
    totals = accumulate(sockets, state)
    save_state(state)
    body = render(totals, gauges(sockets))

    directory = os.path.dirname(target)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tcp-quality-")
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
