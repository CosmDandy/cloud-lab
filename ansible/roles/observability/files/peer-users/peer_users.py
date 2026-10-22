#!/usr/bin/env python3
"""
Lookup metrics that turn client IPs and panel user ids into usernames.

Per-client metrics from the nodes carry `peer` (the client's public IP), and
xray's own counters carry `user` (the panel's numeric id, `email: N` in
access.log). Neither is readable. Names deliberately stay off the nodes, so
the mapping is built here, next to the panel:

    vpn_peer_user{peer="1.2.3.4", user="2", username="CosmDandy"} 1
    vpn_user_info{user="2", username="CosmDandy"} 1

Dashboards and alerts join on it:

    rate(vpn_client_tcp_sent_bytes_total[5m])
      * on (peer) group_left (username) vpn_peer_user

peer -> user comes from xray access logs in Loki; user -> username from the
panel API. Exactly one series per peer: a household behind one NAT gets
`username="A, B"` rather than two series, which would break `group_left`.
Every peer present in the client metrics gets a series, "?" when the logs
have not named it yet — so a join never silently drops a client from an
alert.
"""

import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOKI = os.environ.get("LOKI_URL", "http://loki:3100")
VM = os.environ.get("VM_URL", "http://victoriametrics:8428")
API = os.environ["PANEL_API_URL"]
TOKEN = os.environ["PANEL_API_TOKEN"]
PORT = int(os.environ.get("PORT", "9105"))
REFRESH = 60
# A mapping not refreshed for this long is dropped: mobile carriers recycle
# addresses, and a week-old owner is more likely wrong than right.
TTL = 7 * 86400

ACCESS = (
    'sum by (peer, user) (count_over_time({job="xray"} |= "accepted"'
    " | regexp `from (?:tcp:|udp:)?\\[?(?:::ffff:)?(?P<peer>[0-9a-fA-F.:]+?)\\]?:[0-9]+ accepted"
    " .*email: (?P<user>[0-9]+)`"
    " [%s]))"
)
PEERS = (
    'group by (peer) ({__name__=~"vpn_client_tcp_sent_bytes_total|hy2_tx_bytes_total"})'
)

seen = {}  # peer -> {user: last seen, unix seconds}
names = {}  # user id -> username
body = b""
lock = threading.Lock()


def fetch(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    # Generous: a day of access lines through a regexp takes Loki tens of seconds
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def refresh_seen(window, at=None):
    at = at or time.time()
    q = urllib.parse.urlencode({"query": ACCESS % window, "time": str(int(at))})
    for s in fetch(f"{LOKI}/loki/api/v1/query?{q}")["data"]["result"]:
        m = s["metric"]
        if m.get("peer") and m.get("user"):
            seen.setdefault(m["peer"], {})[m["user"]] = at
    now = time.time()
    for peer in list(seen):
        seen[peer] = {u: t for u, t in seen[peer].items() if now - t < TTL}
        if not seen[peer]:
            del seen[peer]


def refresh_names():
    users = fetch(f"{API}/users?size=1000", {"Authorization": f"Bearer {TOKEN}"})
    names.clear()
    names.update({str(u["id"]): u["username"] for u in users["response"]["users"]})


def live_peers():
    q = urllib.parse.urlencode({"query": PEERS})
    rows = fetch(f"{VM}/api/v1/query?{q}")["data"]["result"]
    return {s["metric"]["peer"] for s in rows if s["metric"].get("peer")}


def label(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def name_of(uid):
    return names.get(uid, f"id{uid}")


def render(peers):
    lines = [
        "# HELP vpn_peer_user Panel user behind a client IP, from xray access logs",
        "# TYPE vpn_peer_user gauge",
    ]
    for peer in sorted(peers | set(seen)):
        # Alphabetical, not by recency: the label is a series identity, and an
        # order that flips whenever the other person connects last would split
        # one household into two series and break every join on it.
        users = sorted(seen.get(peer, {}), key=lambda u: (name_of(u).lower(), u))
        ids = ",".join(users)
        who = ", ".join(name_of(u) for u in users) if users else "?"
        tags = f'peer="{peer}",user="{ids}",username="{label(who)}"'
        lines.append(f"vpn_peer_user{{{tags}}} 1")
    lines += [
        "# HELP vpn_user_info Panel username for a numeric user id",
        "# TYPE vpn_user_info gauge",
    ]
    for uid, name in sorted(names.items(), key=lambda kv: int(kv[0])):
        lines.append(f'vpn_user_info{{user="{uid}",username="{label(name)}"}} 1')
    return ("\n".join(lines) + "\n").encode()


def bootstrap():
    # A day per query, oldest first: one [7d] scan of every access line is
    # heavy enough to time out, and nodes keep exporting counters for peers
    # that went quiet days ago — those still need a name.
    now = time.time()
    for day in range(TTL // 86400 - 1, -1, -1):
        try:
            refresh_seen("1d", now - day * 86400)
        except Exception as exc:  # noqa: BLE001 — a missing day only costs names
            print(f"bootstrap day -{day} failed: {exc}", file=sys.stderr, flush=True)


def loop():
    global body
    bootstrap()
    last_names = 0.0
    while True:
        try:
            if time.time() - last_names > 600:
                refresh_names()
                last_names = time.time()
            refresh_seen("10m")
            out = render(live_peers())
            with lock:
                body = out
        except Exception as exc:  # noqa: BLE001 — keep serving the last good body
            print(f"refresh failed: {exc}", file=sys.stderr, flush=True)
        time.sleep(REFRESH)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — http.server API
        if self.path != "/metrics":
            self.send_error(404)
            return
        with lock:
            out = body
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
