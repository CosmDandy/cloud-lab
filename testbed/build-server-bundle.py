#!/usr/bin/env python3
"""
Merge the 12 single-inbound server-configs into ONE multi-inbound server config
for deployment as a single isolated container on a foreign node (London).

All inbounds keep their unique ports (11001-11012) and tags.
Uses testbed Reality keys — completely separate from production.

Output: testbed/dist/server-bundle.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "server-configs"
OUT = ROOT / "dist"


def main():
    OUT.mkdir(exist_ok=True)
    inbounds = []
    for d in sorted(SRC.glob("*/config.json")):
        cfg = json.loads(d.read_text())
        ib = cfg["inbounds"][0]
        inbounds.append(ib)

    bundle = {
        "log": {"loglevel": "warning"},
        "inbounds": inbounds,
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
    out = OUT / "server-bundle.json"
    out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False))
    print(f"Merged {len(inbounds)} inbounds → {out}")
    for ib in inbounds:
        print(f"  :{ib['port']}  {ib['tag']}")


if __name__ == "__main__":
    main()
