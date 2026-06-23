#!/usr/bin/env python3
"""
Render Xray client config for benchmarking against a specific server-config.

Usage:
    render-client.py <server-config-dir> [--server-host=127.0.0.1]
Prints client config JSON to stdout.
"""
import argparse
import json
import os
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("server_dir")
    ap.add_argument("--server-host", default=os.environ.get("SERVER_HOST", "127.0.0.1"))
    ap.add_argument("--socks-port", type=int, default=10808)
    ap.add_argument("--public-key", default=os.environ.get(
        "REALITY_PUBLIC_KEY", "SZAv4bBy7hbanAfsRQkiHYOpYdwNPEUj4HUnWRzTwSQ"))
    args = ap.parse_args()

    cfg_path = Path(args.server_dir) / "config.json"
    if not cfg_path.exists():
        sys.exit(f"no config at {cfg_path}")
    server = json.loads(cfg_path.read_text())
    inbound = server["inbounds"][0]
    ss = inbound["streamSettings"]
    rs = ss["realitySettings"]
    network = ss["network"]
    user = inbound["settings"]["clients"][0]
    sni = rs["serverNames"][0]
    short_id = rs["shortIds"][1] if len(rs["shortIds"]) > 1 else rs["shortIds"][0]

    stream = {
        "network": network,
        "security": "reality",
        "realitySettings": {
            "show": False,
            "fingerprint": "chrome",
            "serverName": sni,
            "publicKey": args.public_key,
            "shortId": short_id,
            "spiderX": "/",
        },
    }
    if network == "grpc":
        gs = ss["grpcSettings"]
        stream["grpcSettings"] = {
            "serviceName": gs["serviceName"],
            "multiMode": gs.get("multiMode", False),
            "idleTimeout": gs.get("idleTimeout", 60),
            "healthCheckTimeout": gs.get("healthCheckTimeout", 20),
            "permitWithoutStream": gs.get("permitWithoutStream", False),
        }
    elif network == "xhttp":
        xh = ss["xhttpSettings"]
        stream["xhttpSettings"] = {
            "host": xh.get("host", sni),
            "mode": xh.get("mode", "auto"),
            "path": xh["path"],
            "extra": xh.get("extra", {}),
        }

    out = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "socks-in",
                "port": args.socks_port,
                "listen": "0.0.0.0",
                "protocol": "socks",
                "settings": {"udp": True, "auth": "noauth"},
            }
        ],
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": args.server_host,
                            "port": inbound["port"],
                            "users": [
                                {
                                    "id": user["id"],
                                    "encryption": "none",
                                    "flow": user.get("flow", ""),
                                }
                            ],
                        }
                    ]
                },
                "streamSettings": stream,
            },
            {"tag": "block", "protocol": "blackhole"},
        ],
        "routing": {
            "rules": [
                {"type": "field", "outboundTag": "block", "protocol": ["bittorrent"]},
            ]
        },
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
