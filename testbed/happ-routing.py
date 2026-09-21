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
"""

import base64
import json
import sys

# Домены и причины: без причины через полгода не вспомнить, можно ли убрать
REASONS = {
    "hltv.org": "Cloudflare challenge на адреса дата-центров, 21.09.2026",
}


def decode(link):
    raw = link.split("/add/", 1)[1].strip()
    raw += "=" * (-len(raw) % 4)
    return json.loads(base64.b64decode(raw))


def encode(profile):
    # separators без пробелов и то же экранирование слэшей, что в оригинале:
    # ссылка должна отличаться от исходной только содержимым, а не форматом
    raw = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
    return "happ://routing/add/" + base64.b64encode(raw.encode("utf-8")).decode("ascii")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
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
    print(encode(profile))


if __name__ == "__main__":
    main()
