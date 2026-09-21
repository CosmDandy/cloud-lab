#!/usr/bin/env python3
"""
Собирает для Happ ссылку с правилами маршрутизации.

Часть сайтов не открывается именно через VPN: Cloudflare и подобные защиты
встречают адреса дата-центров проверкой, которую браузер не проходит. Лечится
это не на сервере — там запрос уже отдаёт 200, — а выводом такого домена из
туннеля: он идёт с домашнего адреса, и вопросов к нему нет.

Happ хранит правила отдельно от подписки и привязывает к ней, поэтому при
смене серверов список исключений сохраняется. Ссылка ставится один раз.

    python3 happ-routing.py                    показать ссылку
    python3 happ-routing.py --add example.com  добавить домен к списку
"""

import base64
import json
import sys

# Домены, которые ходят мимо туннеля. Каждый — с причиной: без неё через
# полгода никто не вспомнит, можно ли убрать строку.
DIRECT_SITES = [
    "domain:hltv.org",  # Cloudflare challenge на адреса дата-центров, 21.09.2026
]

PROFILE = {
    "Name": "KVT · исключения",
    # true — в туннель идёт всё, кроме перечисленного ниже
    "GlobalProxy": "true",
    "RemoteDNSType": "DoH",
    "RemoteDNSDomain": "https://cloudflare-dns.com/dns-query",
    "DomesticDNSType": "UDP",
    "DomesticDNSIP": "8.8.8.8",
    "Geoipurl": "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat",
    "Geositeurl": "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat",
    "DirectSites": DIRECT_SITES,
    "DirectIp": [],
    "ProxySites": [],
    "ProxyIp": [],
    "BlockSites": [],
    "BlockIp": [],
    "DnsHosts": {},
    "DomainStrategy": "IPIfNonMatch",
    "FakeDNS": "false",
}


def build(profile):
    raw = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
    encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    return raw, f"happ://routing/add/{encoded}"


def main():
    profile = dict(PROFILE)
    if "--add" in sys.argv:
        extra = sys.argv[sys.argv.index("--add") + 1]
        site = extra if ":" in extra else f"domain:{extra}"
        profile["DirectSites"] = [*DIRECT_SITES, site]

    raw, link = build(profile)

    # Обратная проверка: ссылка бесполезна, если Happ не сможет её разобрать
    decoded = json.loads(base64.b64decode(link.split("/add/", 1)[1]))
    assert decoded == profile, "раскодированный профиль не совпал с исходным"

    print("Профиль:")
    print(f"  мимо туннеля: {', '.join(profile['DirectSites'])}")
    print("  остальное:    через VPN (GlobalProxy=true)")
    print(f"  длина json:   {len(raw)} символов, ссылки {len(link)}")
    print("\nСсылка — открыть на устройстве с установленным Happ:\n")
    print(link)


if __name__ == "__main__":
    main()
