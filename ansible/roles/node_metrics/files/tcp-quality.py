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

The previous sample is kept on disk because the collector runs as a timer and
exits between runs — losing it would reset every counter every 30 seconds.

**Closed sockets.** A 30-second sample misses whatever a socket sent after its
last sample, and the whole life of a socket shorter than one interval. Run with
`--events`, this script instead stays up behind `ss -E`, which reports tcp_info
as the kernel destroys each socket, and spools those final counters; every
sample run folds the spool in against the socket's last sampled value.

**Bounded state.** A pair not seen for KEEP_SECONDS is forgotten, and only the
MAX_SERIES most recently active pairs are exported. Ranking by all-time bytes
used to hide a client who was losing packets right now behind someone's
download from last week.

RTT and reordering stay gauges: they describe a state, not an accumulation.
"""

import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from contextlib import contextmanager

# Inbound ports as configured in the panel's config profile. A port missing here
# is simply not reported — node-to-internet sockets are not what we measure.
INBOUNDS = {
    443: "xhttp-stream-443",
    2444: "xhttp-stream",
    2446: "xhttp-packet",
    2054: "vision",
    2056: "vision-nopq",
    2084: "grpc",
}

MAX_SERIES = 50
KEEP_SECONDS = 7 * 86400
STATE_PATH = "/var/lib/node-metrics/tcp-quality.state"
SPOOL_PATH = "/var/lib/node-metrics/tcp-closed.jsonl"
LOCK_PATH = "/var/lib/node-metrics/tcp-closed.lock"
COUNTERS = ("sent", "retrans", "dsack", "retrans_pkts")

# `ss -n` prints IPv4 bare, IPv6 in brackets, and a v4 client on a dual-stack
# listener as [::ffff:a.b.c.d].
SOCKET_HEAD = re.compile(r"(\[[^\]]+\]|[\d.]+):(\d+)\s+(\[[^\]]+\]|[\d.]+):(\d+)")


def address(raw):
    return raw.strip("[]").removeprefix("::ffff:")


def field(pattern, line, default=0.0):
    m = re.search(pattern, line)
    return float(m.group(1)) if m else default


def client_sockets(lines):
    """(peer|inbound|rport, sample) for every inbound socket in `ss -tin` output."""
    key = None
    for line in lines:
        head = SOCKET_HEAD.search(line)
        if head and "bytes_sent" not in line:
            port = int(head.group(2))
            if port in INBOUNDS:
                # Local and remote port together identify the connection; the
                # pair is reused rarely enough that a stale match would have to
                # be deliberate.
                key = f"{address(head.group(3))}|{INBOUNDS[port]}|{head.group(4)}"
            else:
                key = None
            continue
        if key is None or "bytes_sent" not in line:
            continue
        yield (
            key,
            {
                "sent": field(r"\bbytes_sent:(\d+)", line),
                "retrans": field(r"\bbytes_retrans:(\d+)", line),
                "dsack": field(r"\bdsack_dups:(\d+)", line),
                "retrans_pkts": field(r"\bretrans:\d+/(\d+)", line),
                "rtt": field(r"\brtt:([\d.]+)", line),
                "minrtt": field(r"\bminrtt:([\d.]+)", line),
                "reordering": field(r"\breordering:(\d+)", line),
            },
        )
        key = None


@contextmanager
def spool_lock():
    with open(LOCK_PATH, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def events():
    """Daemon mode: spool the final counters of every client socket as it closes."""
    os.makedirs(os.path.dirname(SPOOL_PATH), exist_ok=True)
    # stdbuf: piped ss buffers its output, and an event that arrives after the
    # next sample run has dropped the socket's baseline would be counted whole.
    proc = subprocess.Popen(
        ["stdbuf", "-oL", "ss", "-tinE"], stdout=subprocess.PIPE, text=True
    )
    for key, final in client_sockets(proc.stdout):
        with spool_lock(), open(SPOOL_PATH, "a") as fh:
            fh.write(json.dumps([key, final]) + "\n")
    # ss exits only when its netlink socket breaks; systemd restarts us.
    sys.exit(proc.wait() or 1)


def take_closed():
    with spool_lock():
        try:
            with open(SPOOL_PATH) as fh:
                lines = fh.readlines()
        except FileNotFoundError:
            return []
        os.truncate(SPOOL_PATH, 0)
    closed = []
    for line in lines:
        try:
            closed.append(json.loads(line))
        except ValueError:
            # A line torn by the daemon being killed mid-write.
            continue
    return closed


def load_state():
    try:
        with open(STATE_PATH) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


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
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"ss failed: {exc}", file=sys.stderr)
        return {}
    return dict(client_sockets(out))


def accumulate(sockets, closed, state, now):
    """Fold per-socket growth into counters keyed by (peer, inbound)."""
    # Sockets that vanished from the last sample stay a baseline for one more
    # run, in case their close event reaches the spool only after this one.
    baseline = {**state.get("gone", {}), **state.get("sockets", {})}
    totals = defaultdict(float, state.get("totals", {}))
    seen = state.get("seen", {})
    moved = defaultdict(float)

    def grow(sock_key, current, was):
        peer, inbound, _rport = sock_key.split("|")
        pair = f"{peer}|{inbound}"
        for name in COUNTERS:
            value = current[name]
            # A counter that went backwards means the port was reused by a new
            # connection: treat the whole current value as growth.
            grew = value - was[name] if was and value >= was[name] else value
            totals[f"{pair}|{name}"] += grew
            if name == "sent":
                moved[pair] += grew
        seen[pair] = now

    for sock_key, sample in sockets.items():
        grow(sock_key, sample, baseline.get(sock_key))
    # A socket can close after `ss` sampled it but before the spool was read:
    # its final value then counts from this run's sample, which is dropped.
    live = dict(sockets)
    for sock_key, final in closed:
        grow(sock_key, final, live.pop(sock_key, None) or baseline.get(sock_key))
    closed_keys = {k for k, _ in closed}

    for pair in {k.rsplit("|", 1)[0] for k in totals}:
        seen.setdefault(pair, now)
    for pair, last in list(seen.items()):
        if now - last > KEEP_SECONDS:
            del seen[pair]
            for name in COUNTERS:
                totals.pop(f"{pair}|{name}", None)

    state["gone"] = {
        k: v
        for k, v in state.get("sockets", {}).items()
        if k not in sockets and k not in closed_keys
    }
    state["sockets"] = live
    state["totals"] = dict(totals)
    state["seen"] = seen
    state["closed_total"] = state.get("closed_total", 0) + len(closed)
    return totals, seen, moved


def gauges(sockets):
    """Live state per (peer, inbound): worst RTT inflation, sockets, reordering."""
    live = defaultdict(
        lambda: {"sockets": 0, "rtt": 0.0, "rtt_n": 0, "minrtt": 0.0, "reordering": 0.0}
    )
    for sock_key, s in sockets.items():
        peer, inbound, _ = sock_key.split("|")
        row = live[(peer, inbound)]
        row["sockets"] += 1
        if s["rtt"]:
            row["rtt"] += s["rtt"]
            row["rtt_n"] += 1
        if s["minrtt"]:
            row["minrtt"] = (
                min(row["minrtt"], s["minrtt"]) if row["minrtt"] else s["minrtt"]
            )
        row["reordering"] = max(row["reordering"], s["reordering"])
    return live


def render(totals, seen, moved, live, closed_total):
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
        "# HELP vpn_client_tcp_closed_sockets_total Closed sockets folded in from the event spool",
        "# TYPE vpn_client_tcp_closed_sockets_total counter",
    ]

    by_pair = defaultdict(dict)
    for key, value in totals.items():
        peer, inbound, field_name = key.split("|")
        by_pair[(peer, inbound)][field_name] = value

    def recency(item):
        (peer, inbound), counters = item
        pair = f"{peer}|{inbound}"
        return (-seen.get(pair, 0), -moved.get(pair, 0), -counters.get("sent", 0))

    ranked = sorted(by_pair.items(), key=recency)[:MAX_SERIES]
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
    lines.append(f"vpn_client_tcp_closed_sockets_total {closed_total}")
    return "\n".join(lines) + "\n"


def main():
    if sys.argv[1:] == ["--events"]:
        events()
        return
    target = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "/var/lib/node-exporter/textfile/tcp-quality.prom"
    )

    state = load_state()
    sockets = collect()
    closed = take_closed()
    totals, seen, moved = accumulate(sockets, closed, state, time.time())
    save_state(state)
    body = render(totals, seen, moved, gauges(sockets), state["closed_total"])

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
