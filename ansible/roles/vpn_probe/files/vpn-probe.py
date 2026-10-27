#!/usr/bin/env python3
"""
Every subscription host, probed from inside Russia, pushed to VictoriaMetrics.

Gatus checks the nodes from Sweden: it sees a port open and a node connected
to the panel, and stays green while the Russian path drops a protocol — on
17-18.10 AMS Vision accepted zero connections and every check passed. This
probe connects the way a user does: it takes the user's subscription, builds
an xray client for each host, and fetches a 204 through it.

A protocol is only "dead from Russia" while the direct fetch works: when the
office uplink itself is down, every host fails at once and says nothing about
the VPN. vpn_probe_direct_success carries that baseline.

Results go to /api/v1/import/prometheus as text, so the probe needs neither a
local exporter nor a scraper that can reach an office behind NAT.

The office path drops TLS to our addresses in windows of a few minutes
(measured 26.10.2026: the panel host timed out 26 times out of 69 in a quarter
of an hour while Cloudflare and ya.ru never did). Both the subscription and the
push live on that host, so a run that lands in such a window would vanish. It
does not: the last good subscription is kept and reused, every line carries
the run's own timestamp, and a push that keeps failing is spooled to disk and
sent with the next run — the gap fills in after the fact.
"""

import base64
import json
import os
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import sub2client

SUB_URL = os.environ["VPN_PROBE_SUBSCRIPTION_URL"]
PUSH_URL = os.environ["VPN_PROBE_PUSH_URL"]
PUSH_USER = os.environ["VPN_PROBE_PUSH_USER"]
PUSH_PASSWORD = os.environ["VPN_PROBE_PUSH_PASSWORD"]
INSTANCE = os.environ.get("VPN_PROBE_INSTANCE", socket.gethostname())
XRAY = os.environ.get("VPN_PROBE_XRAY", "/usr/local/bin/xray")
TRIES = int(os.environ.get("VPN_PROBE_TRIES", "3"))
WORKERS = int(os.environ.get("VPN_PROBE_WORKERS", "4"))
SPEED_BYTES = int(os.environ.get("VPN_PROBE_SPEED_BYTES", "5000000"))
STATE = os.environ.get("STATE_DIRECTORY", "/var/lib/vpn-probe")
SUB_CACHE = os.path.join(STATE, "subscription.txt")
SPOOL = os.path.join(STATE, "spool.prom")
PUSH_ATTEMPTS = 10
PUSH_PAUSE = 60
TARGET = "https://www.gstatic.com/generate_204"
SPEED_URL = f"https://speed.cloudflare.com/__down?bytes={SPEED_BYTES}"


def fetch(proxy_port=None, timeout=8):
    """One request; seconds to completion, or None on failure."""
    cmd = ["curl", "-s", "-o", "/dev/null", "--max-time", str(timeout)]
    if proxy_port:
        cmd += ["-x", f"socks5h://127.0.0.1:{proxy_port}"]
    cmd += ["-w", "%{http_code} %{time_total}", TARGET]
    out = subprocess.run(
        cmd, capture_output=True, text=True, check=False
    ).stdout.split()
    return float(out[1]) if len(out) == 2 and out[0] == "204" else None


def speed(proxy_port):
    """Download SPEED_BYTES through the proxy; bits per second, or None."""
    out = subprocess.run(
        [
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "--max-time",
            "30",
            "-x",
            f"socks5h://127.0.0.1:{proxy_port}",
            "-w",
            "%{http_code} %{size_download} %{time_total}",
            SPEED_URL,
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    if len(out) != 3 or out[0] != "200" or int(out[1]) < SPEED_BYTES:
        return None
    return int(out[1]) * 8 / float(out[2])


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_listening(port, deadline=5.0):
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.1)
    return False


def through(entry, measure):
    """Start an xray client for one host and run measure(port) through it."""
    port = free_port()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(sub2client.build_config(entry, port), fh)
        path = fh.name
    proc = subprocess.Popen(
        [XRAY, "run", "-c", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        return measure(port) if wait_listening(port) else None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        os.unlink(path)


def probe(entry):
    def measure(port):
        times = [t for t in (fetch(port) for _ in range(TRIES)) if t is not None]
        return len(times), statistics.median(times) if times else None

    return through(entry, measure) or (0, None)


def load_links():
    """Fresh subscription, or the last good one; (links, fetched_now)."""
    try:
        links = sub2client.load_subscription(SUB_URL)
    except (OSError, urllib.error.URLError) as exc:
        # The subscription domain being unreachable from Russia is a finding
        # of its own: clients cannot refresh their config either.
        print(f"subscription fetch failed: {exc}", file=sys.stderr)
        try:
            with open(SUB_CACHE) as fh:
                return [line for line in fh.read().splitlines() if line], False
        except OSError:
            return [], False
    if links:
        tmp = SUB_CACHE + ".tmp"
        with open(
            os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w"
        ) as fh:
            fh.write("\n".join(links) + "\n")
        os.replace(tmp, SUB_CACHE)
    return links, True


def label(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def host_labels(entry):
    # "🇸🇪 HHH-STO · Vision (sing-box)": the flag is decoration, the rest is the
    # node and the transport exactly as users see them in the app.
    remark = "".join(
        c for c in entry["remark"] if not 0x1F1E6 <= ord(c) <= 0x1F1FF
    ).strip()
    node, _, transport = remark.partition(" · ")
    return f'host="{label(remark)}",node="{label(node)}",transport="{label(transport or remark)}"'


def push(body):
    query = urllib.parse.urlencode(
        [("extra_label", "job=vpn-probe"), ("extra_label", f"instance={INSTANCE}")]
    )
    auth = base64.b64encode(f"{PUSH_USER}:{PUSH_PASSWORD}".encode()).decode()
    req = urllib.request.Request(
        f"{PUSH_URL}?{query}",
        data=body.encode(),
        method="POST",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "text/plain"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


def deliver(body):
    """Push this run together with anything spooled; spool it all on failure."""
    try:
        with open(SPOOL) as fh:
            body = fh.read() + body
    except OSError:
        pass
    for attempt in range(PUSH_ATTEMPTS):
        try:
            push(body)
        except (OSError, urllib.error.URLError) as exc:
            print(f"push {attempt + 1}/{PUSH_ATTEMPTS} failed: {exc}", file=sys.stderr)
            if attempt + 1 < PUSH_ATTEMPTS:
                time.sleep(PUSH_PAUSE)
            continue
        if os.path.exists(SPOOL):
            os.unlink(SPOOL)
        return True
    with open(SPOOL, "w") as fh:
        fh.write(body)
    return False


def main():
    started = time.time()
    # Every line carries the run's start: a spooled run lands where it was
    # measured, not where it was finally delivered.
    ts = int(started * 1000)
    direct = fetch() is not None
    links, fresh = load_links()
    entries = [
        e
        for e in (sub2client.parse_link(link) for link in links)
        if e["scheme"] in ("vless", "hysteria2", "hy2")
    ]
    with ThreadPoolExecutor(WORKERS) as pool:
        results = list(pool.map(probe, entries))
    # One at a time: parallel downloads would split the office uplink and
    # measure each other instead of the path.
    speeds = [
        through(entry, speed) if ok else None
        for entry, (ok, _) in zip(entries, results, strict=True)
    ]

    lines = [
        f"vpn_probe_direct_success {int(direct)}",
        f"vpn_probe_subscription_success {int(fresh)}",
    ]
    for entry, (ok, latency), bps in zip(entries, results, speeds, strict=True):
        tags = host_labels(entry)
        lines.append(f"vpn_probe_success_ratio{{{tags}}} {ok / TRIES:.3f}")
        if latency is not None:
            lines.append(f"vpn_probe_latency_seconds{{{tags}}} {latency:.3f}")
        if bps is not None:
            lines.append(f"vpn_probe_throughput_bits_per_second{{{tags}}} {bps:.0f}")
    lines += [
        f"vpn_probe_hosts {len(entries)}",
        f"vpn_probe_duration_seconds {time.time() - started:.1f}",
        f"vpn_probe_last_run_timestamp_seconds {int(started)}",
    ]
    delivered = deliver("".join(f"{line} {ts}\n" for line in lines))
    print(
        f"{len(entries)} hosts, direct={direct}, subscription fresh={fresh}, "
        f"pushed={delivered}, {time.time() - started:.0f}s"
    )


if __name__ == "__main__":
    main()
