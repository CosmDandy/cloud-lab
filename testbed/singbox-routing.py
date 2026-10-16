"""Add our Happ routing profile ("Sigma Routing v4") to a sing-box config/template.

    python3 singbox-routing.py <in.json> <out.json>

Works on both the panel template and a generated subscription config: it only
touches dns.servers[local], route.rules and route.rule_set.

NOTE: two Happ lists have no sing-box rule set from a trusted source and are
missing here: geosite antifilter-download-community (forced proxy) and
ru-available-only-inside (forced direct). runetfreedom publishes geosite only
as .dat/.txt; SagerNet's sing-geosite does not carry these categories.
"""

import json
import sys

PROXY = "→ Remnawave"
SG = "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set"
GI = "https://raw.githubusercontent.com/runetfreedom/russia-blocked-geoip/release/srs"


def rs(tag, url):
    return {
        "tag": tag,
        "type": "remote",
        "format": "binary",
        "url": url,
        "update_interval": "1d",
    }


RULE_SETS = [
    rs(f"geosite-{c}", f"{SG}/geosite-{c}.srs")
    for c in (
        "category-ru",
        "yandex",
        "mailru",
        "mailru-group",
        "vk",
        "category-gov-ru",
        "category-ads-all",
    )
] + [
    rs("geoip-ru-blocked", f"{GI}/ru-blocked.srs"),
    rs("geoip-ru", f"{GI}/ru.srs"),
]

DIRECT_SITES = [
    t["tag"]
    for t in RULE_SETS
    if t["tag"].startswith("geosite-") and t["tag"] != "geosite-category-ads-all"
]

# Same order as Happ's RouteOrder proxy-direct-block. No resolve step: with
# fakeip a domain connection has no real IP, so IP rules only catch IP-literal
# traffic, and resolving every unmatched domain first would add a DNS round trip
# to each new site. Russian sites are caught by domain instead.
MESH = ["100.64.0.0/10", "fd7a:115c:a1e0::/48"]
RULES = [
    {"ip_cidr": MESH, "outbound": "direct"},
    {"rule_set": ["geoip-ru-blocked"], "outbound": PROXY},
    {"domain_suffix": ["ru", "su", "xn--p1ai"], "outbound": "direct"},
    {"rule_set": DIRECT_SITES, "outbound": "direct"},
    {"rule_set": ["geoip-ru"], "outbound": "direct"},
    {"rule_set": ["geosite-category-ads-all"], "action": "reject"},
]

src, dst = sys.argv[1], sys.argv[2]
cfg = json.load(open(src))

# Happ resolves direct domains through Yandex DNS; Cloudflare from Russia can
# hand out foreign edges for Russian services.
for s in cfg["dns"]["servers"]:
    if s["tag"] == "local":
        s.clear()
        s.update({"tag": "local", "type": "udp", "server": "77.88.8.8"})

# Tailnet addresses must not enter the tun at all: the "direct" outbound binds
# to the physical interface, so a packet for 100.x would leave via Wi-Fi
# instead of tailscaled's own utun. Excluding the routes leaves them to it.
for ib in cfg["inbounds"]:
    if ib["type"] == "tun":
        ib["route_exclude_address"] = MESH

route = cfg["route"]
base = [
    r
    for r in route["rules"]
    if r.get("outbound") != "direct" or not r.get("ip_is_private")
]
private = [r for r in route["rules"] if r.get("ip_is_private")]
route["rules"] = base + private + RULES
route["rule_set"] = RULE_SETS
route["final"] = PROXY

json.dump(cfg, open(dst, "w"), ensure_ascii=False, indent=1)
print(f"{len(route['rules'])} rules, {len(RULE_SETS)} rule sets -> {dst}")
