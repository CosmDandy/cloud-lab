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
TARGET = "https://www.gstatic.com/generate_204"


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


def probe(entry):
    port = free_port()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(sub2client.build_config(entry, port), fh)
        path = fh.name
    proc = subprocess.Popen(
        [XRAY, "run", "-c", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        if not wait_listening(port):
            return 0, None
        times = [t for t in (fetch(port) for _ in range(TRIES)) if t is not None]
        return len(times), statistics.median(times) if times else None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        os.unlink(path)


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


def push(lines):
    query = urllib.parse.urlencode(
        [("extra_label", "job=vpn-probe"), ("extra_label", f"instance={INSTANCE}")]
    )
    auth = base64.b64encode(f"{PUSH_USER}:{PUSH_PASSWORD}".encode()).decode()
    req = urllib.request.Request(
        f"{PUSH_URL}?{query}",
        data=("\n".join(lines) + "\n").encode(),
        method="POST",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "text/plain"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


def main():
    started = time.time()
    direct = fetch() is not None
    lines = [f"vpn_probe_direct_success {int(direct)}"]
    try:
        links = sub2client.load_subscription(SUB_URL)
    except (OSError, urllib.error.URLError) as exc:
        # The subscription domain being unreachable from Russia is a finding
        # of its own: clients cannot refresh their config either.
        print(f"subscription fetch failed: {exc}", file=sys.stderr)
        links = None
    lines.append(f"vpn_probe_subscription_success {int(links is not None)}")

    entries = [
        e
        for e in (sub2client.parse_link(link) for link in links or [])
        if e["scheme"] in ("vless", "hysteria2", "hy2")
    ]
    with ThreadPoolExecutor(WORKERS) as pool:
        results = list(pool.map(probe, entries))
    for entry, (ok, latency) in zip(entries, results, strict=True):
        tags = host_labels(entry)
        lines.append(f"vpn_probe_success_ratio{{{tags}}} {ok / TRIES:.3f}")
        if latency is not None:
            lines.append(f"vpn_probe_latency_seconds{{{tags}}} {latency:.3f}")
    lines += [
        f"vpn_probe_hosts {len(entries)}",
        f"vpn_probe_duration_seconds {time.time() - started:.1f}",
        f"vpn_probe_last_run_timestamp_seconds {int(time.time())}",
    ]
    push(lines)
    print(f"{len(entries)} hosts, direct={direct}, {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
