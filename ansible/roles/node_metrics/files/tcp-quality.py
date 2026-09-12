#!/usr/bin/env python3
"""
Quality of every client TCP connection, as a node-exporter textfile.

Node-level retransmit ratio answers "something is wrong somewhere". This answers
"this client on this inbound is losing 9% right now" — which is the difference
between a graph and an actionable one. The kernel already tracks it per socket;
`ss -ti` just exposes what is there.

Two numbers matter beyond the loss ratio:

  * rtt/minrtt — how much the path is buffering under load. A value of 1 means
    an idle path; 3 means packets are sitting in someone's queue, which is what
    a saturated uplink looks like before it starts dropping.
  * dsack/reordering — whether the "loss" is real. DSACK means a retransmitted
    packet did arrive: TCP gave up on it too early because packets came out of
    order. High reordering with high DSACK is a multipath artefact, not a lossy
    link, and swapping transports will not help.

Output goes to the textfile collector directory, written atomically so a scrape
never sees a half-written file.
"""

import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict

# Inbound ports as configured in the panel's config profile. A port missing here
# is simply not reported — this is deliberate, node-to-internet sockets are not
# what we are measuring.
INBOUNDS = {
    443: "xhttp-stream-443",
    2444: "xhttp-stream",
    2446: "xhttp-packet",
    2054: "vision",
    2084: "grpc",
}

# Reporting every client unbounded would let a scan inflate series count without
# limit; the busiest ones are the only ones worth a time series anyway.
MAX_SERIES = 50

SOCKET_HEAD = re.compile(
    r"\[?(?:::ffff:)?([\d.]+)\]?:(\d+)\s+\[?(?:::ffff:)?([\d.]+)\]?:\d+"
)


def field(pattern, line, default=0.0):
    m = re.search(pattern, line)
    return float(m.group(1)) if m else default


def collect():
    """Aggregate per (peer, inbound). One client holds many sockets at once."""
    try:
        out = subprocess.run(
            ["ss", "-tin", "state", "established"],
            capture_output=True, text=True, timeout=20, check=False,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"ss failed: {exc}", file=sys.stderr)
        return {}

    stats = defaultdict(lambda: defaultdict(float))
    key = None
    for line in out:
        head = SOCKET_HEAD.search(line)
        if head and "bytes_sent" not in line:
            port = int(head.group(2))
            key = (head.group(3), INBOUNDS[port]) if port in INBOUNDS else None
            continue
        if key is None or "bytes_sent" not in line:
            continue

        s = stats[key]
        s["sockets"] += 1
        s["sent"] += field(r"\bbytes_sent:(\d+)", line)
        s["retrans_bytes"] += field(r"\bbytes_retrans:(\d+)", line)
        s["dsack"] += field(r"\bdsack_dups:(\d+)", line)
        # retrans reads as "current/total"; the total is the one that accumulates
        s["retrans_pkts"] += field(r"\bretrans:\d+/(\d+)", line)
        rtt = field(r"\brtt:([\d.]+)", line)
        minrtt = field(r"\bminrtt:([\d.]+)", line)
        s["rtt_sum"] += rtt
        s["rtt_n"] += 1 if rtt else 0
        s["minrtt"] = min(s["minrtt"], minrtt) if s["minrtt"] else minrtt
        s["reordering"] = max(s["reordering"], field(r"\breordering:(\d+)", line))
        s["delivery"] = max(s["delivery"], field(r"\bdelivery_rate:(\d+)", line))
        key = None
    return stats


def render(stats):
    lines = [
        "# HELP vpn_client_tcp_sockets Established TCP sockets per client and inbound",
        "# TYPE vpn_client_tcp_sockets gauge",
        "# HELP vpn_client_tcp_retrans_ratio Percent of bytes retransmitted",
        "# TYPE vpn_client_tcp_retrans_ratio gauge",
        "# HELP vpn_client_tcp_rtt_ms Mean smoothed RTT across the client's sockets",
        "# TYPE vpn_client_tcp_rtt_ms gauge",
        "# HELP vpn_client_tcp_rtt_inflation Current RTT divided by the path minimum",
        "# TYPE vpn_client_tcp_rtt_inflation gauge",
        "# HELP vpn_client_tcp_reordering Kernel reordering estimate, 3 is the default",
        "# TYPE vpn_client_tcp_reordering gauge",
        "# HELP vpn_client_tcp_spurious_ratio Share of retransmits the peer reported as unnecessary",
        "# TYPE vpn_client_tcp_spurious_ratio gauge",
        "# HELP vpn_client_tcp_delivery_bps Best delivery rate observed",
        "# TYPE vpn_client_tcp_delivery_bps gauge",
    ]

    ranked = sorted(stats.items(), key=lambda kv: -kv[1]["sent"])[:MAX_SERIES]
    for (peer, inbound), s in ranked:
        tags = f'peer="{peer}",inbound="{inbound}"'
        sent = s["sent"] or 1
        rtt = s["rtt_sum"] / s["rtt_n"] if s["rtt_n"] else 0
        inflation = rtt / s["minrtt"] if s["minrtt"] else 0
        spurious = s["dsack"] / s["retrans_pkts"] if s["retrans_pkts"] else 0
        lines += [
            f"vpn_client_tcp_sockets{{{tags}}} {int(s['sockets'])}",
            f"vpn_client_tcp_retrans_ratio{{{tags}}} {100 * s['retrans_bytes'] / sent:.4f}",
            f"vpn_client_tcp_rtt_ms{{{tags}}} {rtt:.3f}",
            f"vpn_client_tcp_rtt_inflation{{{tags}}} {inflation:.3f}",
            f"vpn_client_tcp_reordering{{{tags}}} {int(s['reordering'])}",
            f"vpn_client_tcp_spurious_ratio{{{tags}}} {spurious:.4f}",
            f"vpn_client_tcp_delivery_bps{{{tags}}} {int(s['delivery'])}",
        ]
    lines.append(f"vpn_client_tcp_series_total {len(ranked)}")
    return "\n".join(lines) + "\n"


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "/var/lib/node-exporter/textfile/tcp-quality.prom"
    body = render(collect())

    directory = os.path.dirname(target)
    os.makedirs(directory, exist_ok=True)
    # Rename is atomic within a filesystem, so the collector either sees the
    # previous file or the complete new one, never a truncated read.
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
