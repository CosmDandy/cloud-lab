"""Build client configs per variant for the sleep/wake bench (sto-01 hosts).

Takes one user's real subscription (v2ray-json) and applies each variant's
client-side tweak to the matching sto-01 outbound. The configs carry the user's
credentials: they are written 0600 and must be deleted after the run.

    python3 2026-10-23-sleep-wake-configs.py <panel-token-file> <user-id> <out-dir>
"""

import copy
import json
import os
import sys
import urllib.request
from pathlib import Path

TOKEN = Path(sys.argv[1]).read_text().strip()
USER_ID = sys.argv[2]
OUT = Path(sys.argv[3])
req = urllib.request.Request(
    "https://vpn.cosmdandy.dev/api/users?size=500&start=0",
    headers={"Authorization": f"Bearer {TOKEN}"},
)
with urllib.request.urlopen(req, timeout=60) as r:
    users = json.loads(r.read())["response"]["users"]
user = next(u for u in users if str(u["id"]) == USER_ID)
req = urllib.request.Request(
    user["subscriptionUrl"] + "/v2ray-json", headers={"User-Agent": "v2rayN/7.0"}
)
with urllib.request.urlopen(req, timeout=60) as r:
    configs = {c["remarks"]: c for c in json.loads(r.read())}


def base(remark):
    c = configs[f"🇸🇪 HHH-STO · {remark}"]
    return copy.deepcopy(next(o for o in c["outbounds"] if o.get("tag") == "proxy"))


def ss(o):
    return o.setdefault("streamSettings", {})


def xmux(o):
    return ss(o)["xhttpSettings"].setdefault("extra", {}).setdefault("xmux", {})


def tweak(o, path, value):
    *head, last = path
    d = o
    for k in head:
        d = d.setdefault(k, {})
    d[last] = value
    return o


V = {}
V["vision"] = base("Vision")
V["xhttp"] = base("XHTTP-Stream")
V["xhttp-ka10"] = base("XHTTP-Stream")
xmux(V["xhttp-ka10"])["hKeepAlivePeriod"] = 10
V["xhttp-ut8"] = tweak(
    base("XHTTP-Stream"), ["streamSettings", "sockopt", "tcpUserTimeout"], 8000
)
V["xhttp-ka10-ut8"] = tweak(
    base("XHTTP-Stream"), ["streamSettings", "sockopt", "tcpUserTimeout"], 8000
)
xmux(V["xhttp-ka10-ut8"])["hKeepAlivePeriod"] = 10
V["xhttp-ka5"] = base("XHTTP-Stream")
xmux(V["xhttp-ka5"])["hKeepAlivePeriod"] = 5
V["xhttp-ut4"] = tweak(
    base("XHTTP-Stream"), ["streamSettings", "sockopt", "tcpUserTimeout"], 4000
)
V["grpc"] = base("gRPC")
V["grpc-hc"] = base("gRPC")
ss(V["grpc-hc"])["grpcSettings"].update({"idle_timeout": 10, "health_check_timeout": 5})
V["grpc-ut8"] = tweak(
    base("gRPC"), ["streamSettings", "sockopt", "tcpUserTimeout"], 8000
)
V["hy2"] = base("HY2 Masq")
V["hy2-idle10"] = tweak(
    base("HY2 Masq"),
    ["streamSettings", "finalmask", "quicParams", "maxIdleTimeout"],
    10,
)

OUT.mkdir(parents=True, exist_ok=True)
for i, (name, o) in enumerate(V.items()):
    cfg = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "socks",
                "listen": "127.0.0.1",
                "port": 11000 + i,
                "protocol": "socks",
                "settings": {"udp": False},
            }
        ],
        "outbounds": [o, {"tag": "direct", "protocol": "freedom"}],
    }
    p = OUT / f"{name}.json"
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    print(f"{name:16} socks 127.0.0.1:{11000 + i}")
