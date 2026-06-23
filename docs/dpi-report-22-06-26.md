# DPI / VLESS-Reality status report — 22 июня 2026

Обновление к `docs/dpi-report-27-02-26.md`. Покрывает изменения март–июнь 2026 + аудит текущей конфигурации.

---

## ⚙️ Implementation status — выполнено к 23 июня 2026

Трекинг: что из этого отчёта реально сделано (чтобы при следующем заходе была отправная точка).

**Сделано:**
- ✅ **Инбаунды пересобраны.** Старый набор (Vision/gRPC/XHTTP/XHTTP-Opt + DoT, все SNI swisscom, без sockopt) заменён на 4 чистых, по данным тестбеда:
  - `VLESS-Vision` (:2054, SNI googletagmanager) — sockopt, **без testpre** (testpre давал −29%)
  - `VLESS-gRPC` (:2084, SNI update.googleapis) — multiMode + sockopt
  - `VLESS-XHTTP-Stream` (:2444, SNI dl.google) — stream-up + xmux + sockopt
  - `VLESS-XHTTP-Packet` (:2446, SNI swisscom) — packet-up + xmux + sockopt
- ✅ **shortIDs сокращены до 5**, `mldsa65Seed` оставлен (research: backward-compatible, вреда без advertising нет).
- ✅ **sockopt везде** (TFO + BBR + keepalive 300/30, MPTCP off) — на Vision дал +26%, на gRPC +56% (тестбед).
- ✅ **Ansible-роль `vpn_tuning`** — sysctl/BBR/fq/буферы 64MB/file-limits мигрированы из cloud-init, применены на miv-ldn-01 (BBR live, проверено).
- ✅ **Terraform + GitHub workflow заморожены** — только `workflow_dispatch`, push в master ничего не катит (VPN-ноды теперь вручную).
- ✅ **Тестбед** (`testbed/`) — LXC-стенд в РФ, бенчмарк 12 конфигов через speed.cloudflare.com. Правильная топология: Xray-серверы на ЗАРУБЕЖНОЙ ноде, клиент в РФ (RU-exit бесполезен — throttle на server→foreign).
- ✅ **Молдавская нода `miv-chi-01` выведена** (хосты удалены, нода удалена из панели). Остался только London.

**Отложено / не делалось:**
- ⏸️ **Xray v26.6.1** — нет образа от RemnaWave (latest = v26.3.27). Текущий рабочий. `mode=auto` XHTTP сломан в Happ — выкинут, оставлены stream-up/packet-up.
- ⏸️ **Hysteria2** — отложено (4 VLESS-транспорта работают; Hy2 как резерв на случай блокировки TCP).
- ⏸️ **Misaka Frankfurt (чистый exit-ASN)** — обсуждается. Решает freeze на IP MivoCloud (см. ниже), не миграция ради скорости.
- ⏸️ **Диверсификация SNI** — частично сделана (4 разных SNI на 4 инбаундах).

## 🔴 Ключевые находки 22–23 июня 2026 (для будущего себя)

1. **Freeze на IP MivoCloud London.** ТСПУ интермиттентно «замораживает» соединения к IP лондонской ноды на больших устойчивых передачах: 5 МБ проходят, 40 МБ стопорятся (1 байт). НЕ 16 KB-freeze (5 МБ ОК), НЕ зависит от протокола (Vision и XHTTP одинаково), НЕ конфиг. Direct к cloudflare не throttled (cloudflare не флагается, MivoCloud-IP флагается). Интермиттентно: иногда 84 Мбит, иногда стоп. **Решение — чистый exit-ASN, не настройки.**

2. **RU-bridge через «белый» IP — ЗАКРЫТАЯ ТЕМА на 2026.** Схема «арендовать VM в Yandex.Cloud/VK Cloud с whitelisted IP → редирект» **не работает** для рядового арендатора:
   - Белые IP в ASN Яндекс-облака (AS200350, ~12 900 адресов) — это зарезервированные /32 под собственные сервисы Яндекса, НЕ общий пул аренды.
   - Официальная докум. Яндекса: облачный ресурс **не попадает в whitelist автоматически**.
   - Свежеарендованная VM = обычный datacenter-IP = режется на mobile в whitelist-режиме.
   - Тру-whitelist IP в аренду не сдают. Для 5 человек городить это бессмысленно.
   - В whitelist-режим (жёсткие учения МТС/Мегафон) надёжно не пробивает ничего самостоятельного — пережидают.

3. **Xray.** Актуальная upstream v26.6.1, у нас v26.3.27 (нет образа RemnaWave). v26.6.1 нужен был для нативного Hy2 inbound + trustedXForwardedFor. Не блокер.

4. **Hysteria2.** Happ её поддерживает (Xray-based), но RemnaWave не генерит Hy2 share-link в подписке (билдер VLESS-only) → раздача вручную. Требует настоящий TLS-cert (Reality не подходит) → отдельный домен + certbot. Отложено: возни много, польза резервная.

5. **mode=auto XHTTP — сломан** в связке Happ/Xray-клиент (handshake fail). Использовать только explicit `packet-up`/`stream-up`.

## 📊 Выводы тестбеда (22 июня, полные данные в `testbed/results/`)

| Параметр | Эффект (измерено через ТСПУ-путь) |
|---|---|
| `sockopt` (TFO+BBR+keepalive) | Vision +26%, gRPC +56% — **нужен везде** |
| `testpre` (Vision) | **−29% — ВРЕДЕН, убран** |
| `xmux` (XHTTP) | +3-4 Мбит + handshake в 3× быстрее (0.08s vs 0.24s) |
| XHTTP mode (auto/packet/stream) | при xmux на скорость почти не влияет; auto сломан → packet-up для RU |
| Потолок | 100 Мбит домашний канал юзера (~84 Мбит верх) |

---

## Текущее состояние инфраструктуры

| Компонент | Значение | Источник |
|---|---|---|
| Panel | RemnaWave @ `vpn.cosmdandy.dev` (версия не определяется через API) | `GET /api/system/stats` |
| Xray-core | **v26.3.27** на обеих нодах | `GET /api/nodes → versions.xray` |
| Remnanode binary | **v2.7.0** | то же |
| Ноды | `miv-chi-01` MD (94.158.245.24), `miv-ldn-01` GB (194.180.158.12) | оба MivoCloud |
| Транспорты | Vision / gRPC / XHTTP / XHTTP-Opt-2087 (Vision-DoT удалён 2026-06-22) | config-profile `VLESS-Reality` |
| Reality dest/SNI | `www.swisscom.ch:443` (XHTTP-Opt тоже) | все 4 активных inbound'а |
| ShortIDs | 8 шт включая пустой `""` | один общий набор |
| `mldsa65Seed` | задан в каждом inbound (Reality post-quantum signing) | один общий |
| `privateKey` Reality | один общий между inbound'ами и нодами | OK |
| Реальные порты inbound'ов | Vision/gRPC/XHTTP — **:443**, XHTTP-Opt — **:2087** | `node.configProfile.activeInbounds.rawInbound.port` |
| Порты в хостах (что видит клиент) | 2053 / 2083 / 8443 / 2087 | `GET /api/hosts` |
| → значит на нодах NAT-редирект 2053→443, 2083→443, 8443→443, 2087 прямой | предположение по фактам | требует проверки `iptables -t nat -L` |

### Замечание про Vision-DoT (residual)
Хост Vision-DoT удалён через API 2026-06-22. Inbound `VLESS-Reality-Vision-DoT` тоже убран PATCH'ем config-профиля. **Однако** в `node.configProfile.activeInbounds` обеих нод он всё ещё перечислен — RemnaWave не пере-синхронизировал ноды. Требуется рестарт нод (или вручную убрать inbound из active set каждой ноды через UI/API), иначе Xray продолжит слушать порт 853.

---

## TL;DR — что изменилось март→июнь 2026

1. **Три новые волны блокировок**: 15 апреля (приложения Ozon/WB/банки начали детектировать VPN-юзеров), 25 мая (multi-protocol волна, gRPC и Hysteria частично пали в Сибири + Москве), 5 июня (крупнейший инцидент, поведенческий DPI с замораживанием при IP+SNI+>3 параллельных хендшейков → 120–600 сек штрафбан).
2. **Vision+TCP** на MSK/SPB home/mobile — практически мёртв. Держать только как fallback.
3. **Connection freezing** (~16 KB / 25 пакетов) расширил scope ASN-блоклиста, теперь включает все datacenter-сети (Hetzner/DO/OVH/AWS/Vultr/Cloudflare/Oracle).
4. **mldsa65 (Reality cert signing)** — community-консенсус: **не нужен**, если cert dest не маленький (<3500 байт). На `www.swisscom.ch` (обычный enterprise cert) — оверкилл и риск раздуть собственный cert до фингерпринтового размера.
5. **VLESS Post-Quantum Encryption** (`mlkem768x25519plus`, PR #5067) — это **другой** PQ-слой, на уровне VLESS, не Reality. Стабилен в Xray, но клиенты (sing-box, mihomo, V2Box) ещё не парсят. Hiddify с Xray-ядром — должно работать.
6. **uTLS обновлён** 30 мая (PR #6181) — в подписку клиента закладывать `chrome_133` или `random_modern`, не голый `chrome`.
7. **`trustedXForwardedFor`** теперь обязателен для XHTTP/WS/gRPC inbound'ов (PR #6309, v26.5.x+).
8. **Hysteria 2.9.2** (23 мая) — Gecko obfuscation (фрагментация QUIC handshake), прямой ответ на UDP DPI. Xray v26.3.27+ умеет Hy2 inbound сам, отдельный бинарь не нужен.
9. **Aeza** в декабре 2025 начала **сама блокировать VPN-серверы клиентов**. **PQ.Hosting → Stark Industries → THE.Hosting** — голландский FIOD изъял 800 серверов 18–22 мая 2026.
10. **RU-bridge ENTRY/EXIT chain** через дешёвый RU VPS (Yandex.Cloud / VK Cloud / Selectel preemptible) → зарубежный exit — стал де-факто стандартом устойчивости для мобильных операторов с CIDR-whitelist.

---

## Архитектура атаки TSPU (июнь 2026)

Поведенческий DPI с AND-логикой:
1. ASN/CIDR сервера в "подозрительных" (Hetzner, DO, OVH, AWS, Vultr — а с мая 2026 и российские облака)
2. TLS-fingerprint == Chrome через uTLS (старая версия, до обновления 30 мая 2026)
3. \>3 параллельных TLS-handshake к одному SNI с короткими интервалами
→ молчаливый дроп пакетов ~120 с, при попытке переключиться — до 600 с штраф.

Двухстадийная enforcement: **Recognition** (логирование 5–15 мин) → **Enforcement** (центральная CSU выдаёт обновлённый blocklist в TSPU).

ML-классификатор (₽2.27 B бюджет) работает в продакшене с tiered моделью: SNI fast-match → стат-анализ → ML → deep reconstruction. При peak load classifier деградирует — это объясняет интермиттентные пробои.

---

## Применительно к стеку проекта

### Что работает в нашу пользу
- **MivoCloud (AS39798)** не в стандартных RU CIDR-блоклистах. Уникальный ASN — это объясняет, почему London 30 Мбит/с vs 10–15 Мбит/с с Hetzner.
- **3 транспорта** (gRPC + 2× XHTTP) дают protocol agility — выпадение одного не убивает доступ.
- **xhttpSettings уже корректные**: `xPaddingBytes "500-2500"`, `scMaxBufferedPosts 30`, `scMaxEachPostBytes 1000000`, `scMinPostsIntervalMs 30`, `scStreamUpServerSecs "20-80"`, `noSSEHeader true`. Это норма community 2026.
- **gRPC settings** норма: `multiMode false`, `idleTimeout 60`, `healthCheckTimeout 20`.

### Что слабые места
1. **Xray v26.3.27 vs текущая v26.6.1** — 3 минорных релиза отставания. v26.5+ обязал `trustedXForwardedFor`; v26.5.30+ добавил `sessionIDLength` для XHTTP; v26.6.x — фиксы XHTTP packet counting.
2. **`xhttpSettings.mode = "auto"`** — для России community рекомендует `"packet-up"` (короткие коннекты обходят 16-KB freeze).
3. **Нет `xmux` блока** в xhttpSettings.extra. Это значит дефолтный мультиплексинг — можно явно задать `maxConcurrency 16-32`.
4. **Нет `sockopt`** на inbound'ах (TFO, keepalive, BBR).
5. **SNI монокультура** — все 4 inbound'а на `www.swisscom.ch`. Community рекомендует diversification: микс с Go-based сервисами (`dl.google.com`, `www.googletagmanager.com`) — они Aparecium-immune (Go HTTP/2 не шлёт NewSessionTicket).
6. **ShortIDs 8 шт с пустым** — спорный момент: один источник советует убрать пустой как фингерпринт, другой — оставить. Рабочий компромисс — оставить пустой, сократить до 5.
7. **mldsa65Seed** на Reality + Swisscom dest — оверкилл, risk-neutral. Можно убрать.
8. **Vision-DoT inbound в activeInbounds нод** — после удаления через API не пере-синхронизирован. Рестартануть ноды.
9. **Нет Hysteria2** — единственный класс трафика, который пробивает на МТС/Мегафон mobile в RU.
10. **Sysctl дефолтный** (предположение).

### Не slabnesti, но возможности
- **Третья нода в Стокгольме** (Misaka AS57695 или HostHatch AS22769) — RTT до МСК 25 мс vs 50 мс из Лондона, потенциально 60–100 Мбит/с.
- **RU-bridge** для mobile-пользователей (отдельная фаза).

---

## План действий

### P1 — На неделе

```bash
# 1. sysctl (на обеих нодах)
cat > /etc/sysctl.d/99-xray.conf <<'EOF'
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.core.rmem_max = 67108864
net.core.wmem_max = 67108864
net.ipv4.tcp_rmem = 4096 262144 67108864
net.ipv4.tcp_wmem = 4096 262144 67108864
net.ipv4.tcp_window_scaling = 1
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_notsent_lowat = 131072
net.ipv4.tcp_fastopen = 3
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 32768
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1
fs.file-max = 2097152
EOF
sysctl -p /etc/sysctl.d/99-xray.conf
echo '* soft nofile 1048576' >> /etc/security/limits.conf
echo '* hard nofile 1048576' >> /etc/security/limits.conf
```

```text
# 2. Обновить Xray-core на нодах до v26.6.1
# В RemnaWave: Nodes → выбрать ноду → Update → выбрать v26.6.1
# (или через CLI на ноде: docker pull ghcr.io/teddysun/xray:v26.6.1 + restart)

# 3. После удаления Vision-DoT — рестартануть Xray на обеих нодах,
#    чтобы убрать residual inbound из activeInbounds. В RemnaWave UI:
#    Nodes → каждая → Restart Xray.

# 4. ShortIDs: убрать дубликаты/сократить до 5
#    В config-profile patch:
#    "shortIds": ["", "5327c3a970c846a7", "98c18470", "7bc0ae1d", "99595e66"]
```

### P2 — 1–2 недели (правки конфига)

**XHTTP/XHTTP-Opt inbound'ы** — добавить `mode`, `xmux`, `sessionIDLength`, `sockopt`:
```json
"xhttpSettings": {
  "host": "www.swisscom.ch",
  "mode": "packet-up",        // было "auto"
  "path": "/Z4P5RGWuFA",
  "sessionIDLength": 8,         // новое (v26.5.30+)
  "extra": {
    "noSSEHeader": true,
    "xPaddingBytes": "500-2500",
    "scMaxBufferedPosts": 30,
    "scMaxEachPostBytes": 1000000,
    "scMinPostsIntervalMs": 30,
    "scStreamUpServerSecs": "20-80",
    "xmux": {
      "maxConcurrency": "16-32",
      "hMaxRequestTimes": "600-900",
      "hMaxReusableSecs": "1800-3000"
    }
  }
},
"sockopt": {
  "tcpFastOpen": true,
  "tcpcongestion": "bbr",
  "tcpNoDelay": true,
  "tcpKeepAliveIdle": 300,
  "tcpKeepAliveInterval": 30,
  "tcpMptcp": false,
  "trustedXForwardedFor": ["127.0.0.1"]
}
```

**Vision inbound** — добавить экспериментальные anti-fingerprint флаги:
```json
"flow": "xtls-rprx-vision",
"testpre": true,
"testseed": "<random hex 16 byte>"
```

**Диверсификация SNI** — пересоздать inbound'ы:

| Inbound | Новый dest/SNI | Обоснование |
|---|---|---|
| Vision | `www.microsoft.com:443` / `www.microsoft.com` | "too big to block", защита толпой |
| gRPC | `dl.google.com:443` / `dl.google.com` | Go-based, Aparecium-immune |
| XHTTP | `www.googletagmanager.com:443` | Go-based, Aparecium-immune |
| XHTTP-Opt-2087 | `www.swisscom.ch:443` (оставить) | Швейцарский ASN, вариативность |

**Reality `mldsa65Seed`** — можно убрать (оверкилл при cert dest > 3500 байт). Сохранить для других inbound'ов, где dest имеет малый cert.

**uTLS fingerprint** в хостах — обновить с `chrome` на `chrome_133` или `random_modern` через PATCH хостов.

**Hysteria2 inbound** — добавить в config-profile (Xray v26.6.1 умеет нативно):
```json
{
  "tag": "Hysteria2",
  "port": 36712,
  "protocol": "hysteria2",
  "settings": {
    "password": "<random>",
    "obfs": { "type": "salamander", "password": "<random>" }
  },
  "streamSettings": {
    "security": "tls",
    "tlsSettings": { "alpn": ["h3"], "certificates": [...] }
  },
  "quicParams": {
    "congestion": "bbr"
  }
}
```

### P3 — Архитектурные изменения

1. **Третья нода Misaka Stockholm / HostHatch Stockholm** — ожидаемый прирост скорости ×2–3 за счёт RTT и чистого ASN.
2. **RU-bridge ENTRY** для mobile-пользователей — Yandex.Cloud preemptible (~500₽/мес), VLESS+XHTTP с SNI `ya.ru` или `vkvideo.ru` → форвардит на основные ноды.
3. **VLESS Post-Quantum Encryption** — пилотно на одном inbound + Hiddify-клиент для одного пользователя, проверить совместимость.

### НЕ делать

- **Hetzner / OVH / DO / AWS / Vultr / Oracle / Aeza / PQ.Hosting / Stark / THE.Hosting** — все в той или иной форме под ударом.
- **Кастомные ядра (BBRv3-форки, bbrplus и т.п.)** — выгода 5–12%, риск нестабильности; стоковый BBR на Ubuntu 24.04 LTS достаточен.
- **MPTCP** — TSPU ломает на 90% мобильных операторов RU, выгод нет.
- **Vision как primary** — переводить в fallback only.
- **mldsa65 advertising на клиентских subscription** — большой ClientHello + retry-loop = fingerprint.

---

## Источники

- Habr [990236](https://habr.com/en/articles/990236/) — разбор май 2026, AND-логика
- Habr [990206](https://habr.com/en/articles/990206/) — ENTRY/EXIT chain
- Habr [990208](https://habr.com/en/articles/990208/) — XHTTP transport overview
- Habr [1009542](https://habr.com/ru/articles/1009542/) — как ТСПУ ловит VLESS
- Habr [1047442](https://habr.com/ru/articles/1047442/) — заморозка по fingerprint, июнь 2026
- [net4people/bbs #490](https://github.com/net4people/bbs/issues/490) — новый метод TSPU
- [XTLS/Xray-core v26.3.27](https://github.com/XTLS/Xray-core/releases/tag/v26.3.27)
- [XTLS/Xray-core PR #5067](https://github.com/XTLS/Xray-core/pull/5067) — VLESS PQ Encryption
- [XTLS/Xray-core PR #4915](https://github.com/XTLS/Xray-core/pull/4915) — Reality mldsa65
- [Discussion #5847](https://github.com/XTLS/Xray-core/discussions/5847) — VLESS Encryption + Reality + mldsa65 + XHTTP
- [Aparecium #4778](https://github.com/XTLS/Xray-core/issues/4778)
- [Hysteria v2.9.2 Gecko](https://github.com/apernet/hysteria/releases/tag/app%2Fv2.9.2)
- [Stark Industries seizure 18-22.05.2026](https://www.thecybersignal.com/stark-industries-bulletproof-hosting-netherlands-server-seizure-2026/)
- [Aeza блокирует VPN-серверы клиентов](https://habr.com/ru/news/973644/)
- [ACF March 2026 report](https://fbk.info/files/acf-internet-report-EN.pdf)
- [Mediazona — Russia internet censorship 2026](https://en.zona.media/article/2026/04/07/russian_internet_censorship_2026)
- [ntc.party — какие протоколы выжили](https://ntc.party/t/24845)
- [Xeovo Hub — VLESS TLS handshake hardening](https://hub.xeovo.com/posts/132-russia-widespread-vless-outages-due-to-tls-handshake-blockingdegradation-request-tlstransport-hardening-and-anti-probing)
