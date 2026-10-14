#!/usr/bin/env python3
"""
Добавляет домены в существующий профиль маршрутизации Happ.

Часть сайтов не открывается именно через VPN: Cloudflare и подобные защиты
встречают адреса дата-центров проверкой, которую браузер не проходит. На
сервере чинить нечего — оттуда сайт отдаёт 200. Лечится выводом домена из
туннеля: он идёт с домашнего адреса, к которому вопросов нет.

Скрипт не сочиняет профиль с нуля, а правит существующий: берёт ссылку
happ://routing/add/…, добавляет домены в DirectSites и печатает новую.
Так сохраняются все настройки — DNS, geo-файлы, порядок правил, — которые
в самодельном профиле пришлось бы угадывать.

    python3 happ-routing.py '<happ://routing/add/…>' hltv.org
    python3 happ-routing.py '<ссылка>' hltv.org example.com --name 'Новое имя'
    python3 happ-routing.py '<ссылка>' --incy

--incy печатает тот же профиль для INCY: поля те же, но часть ключей
написана иначе, а флаги — строками (docs.incy.cc/en/routing).
"""

import base64
import json
import sys

# Домены и причины: без причины через полгода не вспомнить, можно ли убрать
REASONS = {
    "hltv.org": "Cloudflare challenge на адреса дата-центров, 21.09.2026",
}


# Ключ Happ → ключ INCY. Остальные совпадают.
INCY_KEYS = {
    "RemoteDNSIp": "RemoteDNSIP",
    "DomesticDNSIp": "DomesticDNSIP",
    "FakeDns": "FakeDNS",
    "GeositeUrl": "Geositeurl",
    "GeoipUrl": "Geoipurl",
    "UseChunkFiles": "useChunkFiles",
}
# У INCY эти поля строковые: "true", "1700000000"
INCY_STRINGS = ("GlobalProxy", "FakeDNS", "LastUpdated")


def to_incy(profile):
    out = {INCY_KEYS.get(k, k): v for k, v in profile.items()}
    for k in INCY_STRINGS:
        if isinstance(out.get(k), bool):
            out[k] = "true" if out[k] else "false"
        elif k in out:
            out[k] = str(out[k])
    return out


def decode(link):
    raw = link.split("/add/", 1)[1].strip()
    raw += "=" * (-len(raw) % 4)
    return json.loads(base64.b64decode(raw))


def encode(profile, scheme="happ"):
    # separators без пробелов и то же экранирование слэшей, что в оригинале:
    # ссылка должна отличаться от исходной только содержимым, а не форматом
    raw = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
    return f"{scheme}://routing/add/" + base64.b64encode(raw.encode("utf-8")).decode(
        "ascii"
    )


def main():
    incy = "--incy" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--name" in sys.argv:
        args.remove(sys.argv[sys.argv.index("--name") + 1])
    if len(args) < (1 if incy else 2):
        print(__doc__)
        raise SystemExit(1)

    link, domains = args[0], args[1:]
    profile = decode(link)

    name = None
    if "--name" in sys.argv:
        name = sys.argv[sys.argv.index("--name") + 1]

    direct = list(profile.get("DirectSites", []))
    added = []
    for d in domains:
        entry = d if ":" in d or d.startswith("*") else f"domain:{d}"
        if entry in direct:
            continue
        direct.append(entry)
        added.append(entry)

    profile["DirectSites"] = direct
    if name:
        profile["Name"] = name

    print(f"профиль: {profile.get('Name')}")
    print(f"порядок правил: {profile.get('RouteOrder', 'не задан')}")
    print(f"добавлено в DirectSites: {', '.join(added) or 'ничего нового'}")
    for d in domains:
        if d in REASONS:
            print(f"   {d}: {REASONS[d]}")
    print(f"\nвсего мимо туннеля: {len(direct)} правил")
    print("\nновая ссылка:\n")
    print(encode(to_incy(profile), "incy") if incy else encode(profile))


if __name__ == "__main__":
    main()
