#!/usr/bin/env python3
"""
Generate 12 Xray server-configs under server-configs/NN-name/config.json
from a single declarative variant matrix.

Run from testbed/ root:
    python3 generate-configs.py
"""
import json
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "server-configs"

# Testbed Reality identity (отдельная от прода)
# Testbed Reality identity — NEVER commit real keys. Provide via env:
#   REALITY_PRIVATE_KEY=$(docker run --rm ghcr.io/xtls/xray-core:latest x25519 | ...)
#   CLIENT_UUID=$(docker run --rm ghcr.io/xtls/xray-core:latest uuid)
REALITY_PRIV = os.environ.get("REALITY_PRIVATE_KEY", "GENERATE_VIA_xray_x25519")
CLIENT_UUID  = os.environ.get("CLIENT_UUID", "00000000-0000-0000-0000-000000000000")
SHORT_IDS    = ["", "00112233"]

SOCKOPT = {
    "tcpFastOpen": True,
    "tcpcongestion": "bbr",
    "tcpNoDelay": True,
    "tcpKeepAliveIdle": 300,
    "tcpKeepAliveInterval": 30,
    "tcpMptcp": False,
}

XHTTP_EXTRA_BASE = {
    "noSSEHeader": True,
    "xPaddingBytes": "100-1000",
    "scMaxBufferedPosts": 30,
    "scMaxEachPostBytes": 1000000,
    "scMinPostsIntervalMs": 30,
    "scStreamUpServerSecs": "20-80",
}
XMUX_BLOCK = {
    "maxConcurrency": "16-32",
    "hMaxRequestTimes": "600-900",
    "hMaxReusableSecs": "1800-3000",
}


def reality(sni):
    return {
        "dest": f"{sni}:443",
        "show": False,
        "xver": 0,
        "shortIds": SHORT_IDS,
        "privateKey": REALITY_PRIV,
        "serverNames": [sni],
    }


def vision(idx, name, sockopt, testpre):
    sni = "www.googletagmanager.com"
    rs = reality(sni)
    if testpre:
        rs["testpre"] = True
        rs["testseed"] = secrets.token_hex(16)
    inbound = {
        "tag": f"in-{idx:02d}-{name}",
        "port": 11000 + idx,
        "protocol": "vless",
        "settings": {
            "clients": [{"id": CLIENT_UUID, "flow": "xtls-rprx-vision"}],
            "decryption": "none",
        },
        "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
        "streamSettings": {
            "network": "raw",
            "security": "reality",
            "realitySettings": rs,
        },
    }
    if sockopt:
        inbound["streamSettings"]["sockopt"] = SOCKOPT
    return inbound


def xhttp(idx, name, mode, xmux, sockopt):
    sni = "www.swisscom.ch"
    extra = dict(XHTTP_EXTRA_BASE)
    if xmux:
        extra["xmux"] = XMUX_BLOCK
    inbound = {
        "tag": f"in-{idx:02d}-{name}",
        "port": 11000 + idx,
        "protocol": "vless",
        "settings": {
            "clients": [{"id": CLIENT_UUID}],
            "decryption": "none",
        },
        "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
        "streamSettings": {
            "network": "xhttp",
            "security": "reality",
            "xhttpSettings": {
                "host": sni,
                "mode": mode,
                "path": "/" + secrets.token_hex(5),
                "extra": extra,
            },
            "realitySettings": reality(sni),
        },
    }
    if sockopt:
        inbound["streamSettings"]["sockopt"] = SOCKOPT
    return inbound


def grpc(idx, name, multimode, sockopt):
    sni = "update.googleapis.com"
    inbound = {
        "tag": f"in-{idx:02d}-{name}",
        "port": 11000 + idx,
        "protocol": "vless",
        "settings": {
            "clients": [{"id": CLIENT_UUID}],
            "decryption": "none",
        },
        "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
        "streamSettings": {
            "network": "grpc",
            "security": "reality",
            "grpcSettings": {
                "multiMode": multimode,
                "idleTimeout": 60,
                "serviceName": secrets.token_hex(7),
                "healthCheckTimeout": 20,
                "permitWithoutStream": False,
            },
            "realitySettings": reality(sni),
        },
    }
    if sockopt:
        inbound["streamSettings"]["sockopt"] = SOCKOPT
    return inbound


def make_config(inbound):
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [inbound],
        "outbounds": [
            {"tag": "DIRECT", "protocol": "freedom"},
            {"tag": "BLOCK", "protocol": "blackhole"},
        ],
        "routing": {
            "rules": [
                {"type": "field", "outboundTag": "BLOCK", "protocol": ["bittorrent"]},
            ]
        },
    }


VARIANTS = [
    (1,  "vision-base",        lambda: vision(1,  "vision-base",        sockopt=False, testpre=False)),
    (2,  "vision-sockopt",     lambda: vision(2,  "vision-sockopt",     sockopt=True,  testpre=False)),
    (3,  "vision-testpre",     lambda: vision(3,  "vision-testpre",     sockopt=False, testpre=True)),
    (4,  "vision-full",        lambda: vision(4,  "vision-full",        sockopt=True,  testpre=True)),
    (5,  "xhttp-auto-no",      lambda: xhttp(5,   "xhttp-auto-no",      mode="auto",      xmux=False, sockopt=True)),
    (6,  "xhttp-auto-xmux",    lambda: xhttp(6,   "xhttp-auto-xmux",    mode="auto",      xmux=True,  sockopt=True)),
    (7,  "xhttp-packet-no",    lambda: xhttp(7,   "xhttp-packet-no",    mode="packet-up", xmux=False, sockopt=True)),
    (8,  "xhttp-packet-xmux",  lambda: xhttp(8,   "xhttp-packet-xmux",  mode="packet-up", xmux=True,  sockopt=True)),
    (9,  "xhttp-stream-no",    lambda: xhttp(9,   "xhttp-stream-no",    mode="stream-up", xmux=False, sockopt=True)),
    (10, "xhttp-stream-xmux",  lambda: xhttp(10,  "xhttp-stream-xmux",  mode="stream-up", xmux=True,  sockopt=True)),
    (11, "grpc-base",          lambda: grpc(11,   "grpc-base",          multimode=False, sockopt=False)),
    (12, "grpc-mm-sockopt",    lambda: grpc(12,   "grpc-mm-sockopt",    multimode=True,  sockopt=True)),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    for idx, name, builder in VARIANTS:
        inbound = builder()
        cfg = make_config(inbound)
        d = OUT / f"{idx:02d}-{name}"
        d.mkdir(exist_ok=True)
        with open(d / "config.json", "w") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

        net = inbound["streamSettings"]["network"]
        ss = inbound["streamSettings"]
        meta[f"{idx:02d}-{name}"] = {
            "port": inbound["port"],
            "network": net,
            "sni": ss["realitySettings"]["serverNames"][0],
            "flow": inbound["settings"]["clients"][0].get("flow"),
            "mode": ss.get("xhttpSettings", {}).get("mode"),
            "path": ss.get("xhttpSettings", {}).get("path"),
            "service_name": ss.get("grpcSettings", {}).get("serviceName"),
            "multi_mode": ss.get("grpcSettings", {}).get("multiMode"),
            "sockopt": "sockopt" in ss,
            "xmux": "xmux" in ss.get("xhttpSettings", {}).get("extra", {}),
            "testpre": ss["realitySettings"].get("testpre", False),
        }
        print(f"  ✓ {idx:02d}-{name:<22} port={inbound['port']}  net={net}")

    with open(OUT / "index.json", "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"\nGenerated {len(VARIANTS)} configs into {OUT}")


if __name__ == "__main__":
    main()
