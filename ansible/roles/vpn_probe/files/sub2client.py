#!/usr/bin/env python3
"""
Live Remnawave subscription -> xray client config for one of its hosts.

The input is the very link a real user gets, so what is measured is what
users receive: a mismatch between the server config and the subscription is
itself a finding (that is how HY2 Salamander and Hop turned out dead — the
subscription never handed out the salamander password).

Usage:
    sub2client.py <sub-url|file> --select "HHH-STO · Vision" > client.json
    sub2client.py <sub-url|file> --list

--salamander and --hop-ports separate "the protocol is broken" from "the
subscription left a parameter out": with them the client follows the server
config instead of the link.
"""

import argparse
import base64
import json
import sys
import urllib.parse
import urllib.request

SOCKS_PORT_DEFAULT = 10808


def load_subscription(src: str) -> list[str]:
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "v2rayN/6.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
    else:
        with open(src) as fh:
            body = fh.read()

    # Remnawave serves base64 to v2ray clients; plain text is accepted too, the
    # format depends on the User-Agent and panel settings.
    stripped = "".join(body.split())
    try:
        decoded = base64.b64decode(stripped, validate=True).decode()
    except (ValueError, UnicodeDecodeError):
        decoded = body
    return [line.strip() for line in decoded.splitlines() if "://" in line]


def parse_link(link: str) -> dict:
    head, _, frag = link.partition("#")
    parts = urllib.parse.urlsplit(head)
    query = {k: v[0] for k, v in urllib.parse.parse_qs(parts.query).items()}
    return {
        "scheme": parts.scheme,
        "user": urllib.parse.unquote(parts.username or ""),
        "host": parts.hostname or "",
        "port": parts.port or 0,
        "query": query,
        "remark": urllib.parse.unquote(frag),
        "link": link,
    }


def stream_settings(p: dict) -> dict:
    q = p["query"]
    net = q.get("type", "raw")
    # xray 26 calls this transport raw; links still say tcp.
    ss: dict = {"network": "raw" if net == "tcp" else net}

    if q.get("security") == "reality":
        reality = {
            "serverName": q.get("sni", ""),
            "fingerprint": q.get("fp", "chrome"),
            "publicKey": q.get("pbk", ""),
            "shortId": q.get("sid", ""),
            "spiderX": q.get("spx", ""),
        }
        # pqv is the ML-DSA-65 server signature (xray 25.9+). Without it the
        # client still connects but authenticates the server the old way, and
        # the probe stops matching what a real client does.
        if q.get("pqv"):
            reality["mldsa65Verify"] = q["pqv"]
        ss["security"] = "reality"
        ss["realitySettings"] = reality
    elif q.get("security") == "tls":
        ss["security"] = "tls"
        ss["tlsSettings"] = {"serverName": q.get("sni", p["host"])}

    if ss["network"] == "xhttp":
        xh = {
            "host": q.get("host", ""),
            "path": q.get("path", "/"),
            "mode": q.get("mode", "auto"),
        }
        if q.get("extra"):
            xh["extra"] = json.loads(q["extra"])
        ss["xhttpSettings"] = xh
    elif ss["network"] == "grpc":
        ss["grpcSettings"] = {
            "serviceName": q.get("serviceName", ""),
            "multiMode": q.get("mode") == "multi",
        }

    return ss


def vless_outbound(p: dict) -> dict:
    q = p["query"]
    user = {"id": p["user"], "encryption": q.get("encryption", "none")}
    if q.get("flow"):
        user["flow"] = q["flow"]
    return {
        "tag": "proxy",
        "protocol": "vless",
        "settings": {
            "vnext": [{"address": p["host"], "port": p["port"], "users": [user]}]
        },
        "streamSettings": stream_settings(p),
    }


def hysteria2_outbound(p: dict, salamander: str | None, hop_ports: str | None) -> dict:
    q = p["query"]
    ss: dict = {
        "network": "hysteria",
        "security": "tls",
        "tlsSettings": {"alpn": ["h3"], "serverName": q.get("sni", p["host"])},
        "hysteriaSettings": {"version": 2, "auth": p["user"]},
    }
    # fm is how Remnawave puts finalMask into the link: the whole JSON, as in
    # the server config. Parsed first so the probe checks exactly what a real
    # client receives rather than something assembled by hand.
    if q.get("fm"):
        ss["finalMask"] = json.loads(q["fm"])
    obfs = salamander or q.get("obfs-password")
    if obfs:
        ss["finalMask"] = {"salamander": {"password": obfs}}
    hop = hop_ports or q.get("mport")
    if hop:
        ss["quicParams"] = {"udpHop": {"ports": hop, "interval": "30s"}}
    return {
        "tag": "proxy",
        "protocol": "hysteria",
        "settings": {"version": 2, "address": p["host"], "port": p["port"]},
        "streamSettings": ss,
    }


def build_config(
    p: dict,
    socks_port: int,
    salamander: str | None = None,
    hop_ports: str | None = None,
) -> dict:
    if p["scheme"] == "vless":
        out = vless_outbound(p)
    elif p["scheme"] in ("hysteria2", "hy2"):
        out = hysteria2_outbound(p, salamander, hop_ports)
    else:
        raise ValueError(f"unsupported scheme: {p['scheme']}")

    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "socks-in",
                "port": socks_port,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {"udp": True, "auth": "noauth"},
            }
        ],
        "outbounds": [out],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="subscription URL or a file holding it")
    ap.add_argument("--select", help="remark substring: which host to build")
    ap.add_argument("--list", action="store_true", help="list available hosts")
    ap.add_argument("--socks-port", type=int, default=SOCKS_PORT_DEFAULT)
    ap.add_argument("--salamander", help="obfs password the subscription left out")
    ap.add_argument("--hop-ports", help="port hopping range, e.g. 47000-47100")
    args = ap.parse_args()

    entries = [parse_link(link) for link in load_subscription(args.source)]

    if args.list:
        for e in entries:
            q = e["query"]
            kind = q.get("type", e["scheme"])
            mode = q.get("mode", "")
            print(
                f"{e['remark']}\t{e['scheme']}\t{kind}{'/' + mode if mode else ''}"
                f"\t{e['host']}:{e['port']}"
            )
        return

    if not args.select:
        raise SystemExit("--select or --list is required")

    # An exact match wins over a substring: host names nest ("XHTTP-Packet" is
    # part of "XHTTP-Packet 443"), and a caller passing the full name would
    # otherwise get "2 selected" and silently lose a host per node.
    matched = [e for e in entries if e["remark"] == args.select]
    if not matched:
        matched = [e for e in entries if args.select in e["remark"]]
    if len(matched) != 1:
        names = "\n  ".join(e["remark"] for e in matched) or "(none)"
        raise SystemExit(
            f"--select must pick exactly one host, got {len(matched)}:\n  {names}"
        )

    cfg = build_config(matched[0], args.socks_port, args.salamander, args.hop_ports)
    json.dump(cfg, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
