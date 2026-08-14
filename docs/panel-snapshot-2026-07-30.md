# Снимок боевой панели htz-hel-01 — 2026-07-30

Что настроено в Remnawave на сегодня. До этого файла конфигурация панели не была
описана нигде, кроме её же постгреса: потеряв машину, мы не восстановили бы даже
то, что на ней было настроено руками.

Файл описывает **форму** конфигурации, а не её секреты. Реальные значения ключей
и пароли — в выгрузках, см. «Где лежит состояние».

## Как снято

Всё через `docker exec remnawave-postgres psql`, только чтение. Панель и ноды не
трогались, пользователи ничего не заметили.

```sh
ssh -o BatchMode=yes -o ConnectTimeout=5 -T root@204.168.216.193 \
  'docker exec remnawave-postgres sh -c '\''pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl'\''' \
  > backups/htz-hel-01/remnawave-2026-07-30.dump
```

Дамп проверен полным разбором архива — `pg_restore -f /dev/null` прочитал каждый
блок данных и распаковал его в SQL. Это проверка целостности, а не восстановления:
что дамп развернётся в рабочую панель, доказал бы только настоящий restore, а его
негде делать до появления второй машины.

## Где лежит состояние

`backups/` в `.gitignore` — там открытые секреты и данные пользователей.
Каталог лежит в девконтейнере, то есть **это не бэкап, а копия**: две копии на
двух машинах, обе без ротации и без проверки.

| Файл | Размер | sha256 (начало) |
| --- | --- | --- |
| `backups/htz-hel-01/remnawave-2026-07-30.dump` | 165 KB | `edeef466adfe` |
| `backups/htz-hel-01/control-state-2026-07-30.tar.gz` | 59 KB | `e501d5bb84ba` |

В тарболе:

- `opt/control/` — docker-compose и все `.env` (панель, подписка, traefik,
  headscale, headplane);
- `headscale_data` — `db.sqlite` + WAL, `noise_private.key`,
  `derp_server_private.key`;
- `headplane_data` — `hp_persist.db`;
- `letsencrypt` — `acme.json` с боевыми сертификатами.

SQLite headscale скопирован файлом вместе с `-wal` и `-shm`, а не через
`sqlite3 .backup`: в контейнере headscale нет `sqlite3`. Для headscale это
приемлемо — его решено поднимать с нуля.

## Профиль и инбаунды

Один профиль `VLESS-Reality` (`2cb12440-8073-45aa-bd46-25cefbc6c46d`),
создан 2026-04-15, последняя правка 2026-06-22. Четыре инбаунда, все vless +
reality, все на одной паре ключей (`privateKey` + `mldsa65Seed` — Reality с
пост-квантовой частью, то есть Xray 25.x и новее).

| Тег | Транспорт | Порт | dest / serverName | Особенности |
| --- | --- | --- | --- | --- |
| `VLESS-Vision` | raw | 2054 | `www.googletagmanager.com:443` | — |
| `VLESS-gRPC` | grpc | 2084 | `update.googleapis.com:443` | `serviceName: Cch0KoWA3CfssA`, multiMode, idleTimeout 60 |
| `VLESS-XHTTP-Stream` | xhttp | 2444 | `dl.google.com:443` | `mode: stream-up`, `path: /sZ4P5RGWuFA` |
| `VLESS-XHTTP-Packet` | xhttp | 2446 | `www.swisscom.ch:443` | `mode: packet-up`, `path: /pZ4P5RGWuFA` |

Общее для всех четырёх:

- `shortIds`: пустая строка + `5327c3a970c846a7`, `98c18470`, `7bc0ae1d`,
  `99595e66`;
- `sniffing`: `http`, `tls`, `quic`;
- `sockopt`: `tcpcongestion: bbr`, `tcpFastOpen: true`, `tcpNoDelay: true`,
  `tcpKeepAliveIdle: 300`, `tcpKeepAliveInterval: 30`, `tcpMptcp: false`;
- у обоих xhttp — `xmux` (`maxConcurrency: 16-32`, `hMaxRequestTimes: 600-900`,
  `hMaxReusableSecs: 1800-3000`), `xPaddingBytes: 100-1000`, `noSSEHeader: true`.

Ключи Reality **не приводятся здесь намеренно**. Они в дампе, и восстанавливать
их из документа не нужно: клиенты забирают конфигурацию по ссылке подписки, так
что после пересоздания инбаундов с новыми ключами всё разъедется само — при
условии, что живы пользователи и их UUID подписок.

## Ноды

Все три — HostHatch, порт панель→нода 2222, профиль тот же, множитель 1.

| Имя | Адрес | Страна | Состояние |
| --- | --- | --- | --- |
| `hhh-ams-01` | 85.155.190.66 | NL | подключена |
| `hhh-sto-01` | 167.104.104.131 | SE | подключена |
| `hhh-osl-01` | 91.190.155.237 | NO | подключена |

Каждой ноде выданы все четыре инбаунда — 12 связок.

> `ansible/inventory/cloud.yml` про эти ноды не знает: в группе `vpn_nodes` там
> `miv-chi-01` и `miv-ldn-01` с Mivocloud, которых в панели нет вовсе. Инвентарь
> отстал от реальности минимум на одну смену провайдера.

## Хосты

12 штук — по четыре на ноду, ровно по инбаундам. Порт совпадает с портом
инбаунда, адрес — IP ноды (доменов нет, обращение по адресу).

| Нода | Vision (2054) | gRPC (2084) | XHTTP-Stream (2444) | XHTTP-Packet (2446) |
| --- | --- | --- | --- | --- |
| 🇳🇱 HHH-AMS | вкл | вкл | вкл | вкл |
| 🇸🇪 HHH-STO | вкл | вкл | вкл | вкл |
| 🇳🇴 HHH-OSL | **выкл** | **выкл** | вкл | вкл |

Осло раздаёт только xhttp: Vision и gRPC там выключены.

SNI хоста повторяет `serverName` своего инбаунда, `fingerprint: chrome` —
кроме XHTTP-Packet, где и SNI, и fingerprint пустые. `path` задан только у
XHTTP-Stream (`/sZ4P5RGWuFA`). Ни у одного хоста нет `alpn`, `host`,
`mux_params`, `sockopt_params`, `xhttp_extra_params`; `security_layer: DEFAULT`,
`is_hidden`, `override_sni_from_address`, `keep_sni_blank`, `shuffle_host` — всё
выключено.

> `fingerprint: chrome` — тот самый пункт из отчёта по DPI (`docs/dpi/`):
> есть основания считать, что отпечаток Chrome сам по себе привлекает внимание,
> а Firefox проходит. Проверять это надо на стенде, не на боевых хостах.

## Сквады, пользователи, шаблоны

- Сквады: `Main` (12 пользователей) и `Default-Squad` (1). Оба выдают все
  четыре инбаунда.
- Пользователей 13, все `ACTIVE`. Устройств по HWID — 18, но сам HWID-лимит
  выключен (`hwid_settings.enabled: false`).
- Админ один: `CosmDandy`, роль `ADMIN`.
- API-токенов два — `API` и `Sub`, оба со скоупом `*` и сроком до 2300 года.
  Токен `Sub` — тот, которым `remnawave-subscription-page` ходит в панель
  (`REMNAWAVE_API_TOKEN` в `subscription/.env`).
- Шаблоны подписки: по одному дефолтному на CLASH, MIHOMO, STASH, SINGBOX,
  XRAY_JSON плюс отдельный `xray-json` первым в списке — он и отдаётся.
  В нём маршрутизация: bittorrent, приватные сети, `geosite:category-ru`,
  yandex, mailru, `geosite:category-gov-ru` и `geoip:ru` идут напрямую, реклама
  режется, остальное в туннель.
- `subscription_page_config` — один документ на 115 КБ, редактируется только
  через UI.

## Настройки подписки и панели

`subscription_settings`: `profile_title: CosmDandy`,
`support_link: https://t.me/CosmDandy`, `profile_update_interval: 1`,
`randomize_hosts: true`, `is_show_custom_remarks: true`,
`is_profile_webpage_url_enabled: true`, `serve_json_at_base_subscription: false`.
Правила ответа по User-Agent — стандартный набор Remnawave (браузер → страница,
mihomo/clash/stash/sing-box → свой шаблон, всё прочее → base64).

`remnawave_settings` — **вход только по паролю**:

```
password_settings  {"enabled": true}
passkey_settings   {"enabled": false}
oauth2_settings    все провайдеры (github, yandex, generic, keycloak,
                   pocketid, telegram) — enabled: false
```

Это настройка в базе, а не в `.env`, и в раскатку ролями она не попадает.
После переезда OIDC в панели придётся включать руками через UI — и заводить
клиента как **Generic**, а не Pocket ID: в режиме pocketid панель шлёт
`redirect_uri=null`, и сертифицированный провайдер такой запрос отвергает.

## Переменные окружения работающей схемы

Имена, чтобы было с чем сверять роль `panel`. Значения — в тарболе.

- `opt/control/.env`: `PANEL_DOMAIN`, `SUB_DOMAIN`, `MESH_DOMAIN`,
  `TRAEFIK_DOMAIN`, `POSTGRES_PASSWORD`.
- `opt/control/panel/.env`: `APP_PORT`, `METRICS_PORT`, `API_INSTANCES`,
  `DATABASE_URL`, `REDIS_HOST`, `REDIS_PORT`, `JWT_AUTH_SECRET`,
  `JWT_API_TOKENS_SECRET`, `IS_TELEGRAM_NOTIFICATIONS_ENABLED`, `PANEL_DOMAIN`,
  `FRONT_END_DOMAIN`, `SUB_PUBLIC_DOMAIN`, `IS_DOCS_ENABLED`, `METRICS_USER`,
  `METRICS_PASS`, `WEBHOOK_ENABLED`.
- `opt/control/subscription/.env`: `PORT`, `REMNAWAVE_PANEL_URL`,
  `REMNAWAVE_API_TOKEN`, `TRUST_PROXY`.

`JWT_AUTH_SECRET` в Remnawave 2.8.1 называется именно так — переименования в
`APP_SECRET` не было, вопреки тому, что попадается в пересказах.

## Порядок восстановления

Панель не поднимается из этого документа — она поднимается из дампа. Документ
нужен, чтобы понять, что должно получиться, и заметить расхождение.

1. Развернуть роль `panel` с теми же `JWT_AUTH_SECRET`, `JWT_API_TOKENS_SECRET`,
   `POSTGRES_PASSWORD` (лежат в `host_vars/htz-hel-01/secrets.sops.yaml`) —
   тогда сессии и API-токены переживут перенос.
2. `pg_restore` дампа в пустую базу до первого старта панели: миграции Prisma
   на непустой базе разойдутся с дампом.
3. Сверить с этим файлом: 4 инбаунда, 3 ноды, 12 хостов, 2 сквада, 13
   пользователей, 2 API-токена.
4. Ноды переподключатся сами — CA лежит в таблице `keygen` и приезжает
   вместе с дампом. Пересоздавать сертификаты нод не нужно.

## Чего здесь нет

Бэкапов. Роль `ansible/roles/backup` написана под restic в S3, а бакета и
ключей нет, поэтому она никуда не раскатана и её `assert` на пустых
`backup_s3_*` не даст даже запустить её вхолостую. Пока состояние живёт в
одном экземпляре на самой машине — эта выгрузка разовая и ручная.
