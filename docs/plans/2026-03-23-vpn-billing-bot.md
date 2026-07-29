# Plan: VPN Billing Telegram Bot with Per-User Credentials

## Scope

**Covers:**
- Переход sing-box с shared credentials на per-user (массив `users[]`)
- Telegram-бот (aiogram 3 + SQLite) для управления пользователями и подписками
- Генерация и доставка per-user клиентских конфигов через Telegram
- Автоматические напоминания об оплате и отключение неплательщиков
- Интеграция в существующий docker-compose на VPN-сервере

**НЕ covers:**
- Интеграция с платёжными системами (YooKassa и т.д.) — оплата P2P через СБП, подтверждение вручную
- Web UI / self-service портал
- Per-user трафик-лимиты и мониторинг использования
- Изменения в Terraform (credentials переезжают из Terraform в бота)

## Constraints

- **Масштаб**: 5-20 пользователей (друзья), не коммерческий сервис
- **Хостинг**: тот же CAX11 (2 vCPU ARM, 4 GB RAM) — бот должен быть лёгким
- **Платежи**: P2P (СБП/карта), ручное подтверждение владельцем — без ИП
- **Совместимость**: deploy workflow продолжает работать для инфраструктурных изменений (обновление sing-box, Caddy, route rules). Бот управляет пользователями **независимо** от CI/CD
- **REALITY keys**: `reality_private_key` и `reality_short_id` остаются shared (это серверные ключи шифрования, не user credentials)
- **SALAMANDER_PASSWORD**: остаётся shared (obfuscation layer, не аутентификация)

## Architectural Decision: Bot owns user credentials

Credentials переезжают из Terraform → в бота. Причина:
- Terraform генерирует static credentials при `apply` — не подходит для динамического добавления/удаления пользователей
- Бот генерирует UUID/пароли при `/approve`, хранит в SQLite, обновляет sing-box конфиг и рестартит контейнер
- Deploy workflow по-прежнему управляет серверным конфигом (inbounds, TLS, routing), но секцию `users[]` бот перезаписывает при каждом изменении состава пользователей

**Разделение ответственности:**

| Компонент | Кто управляет | Как |
|-----------|--------------|-----|
| sing-box inbounds/routing | CI/CD (GitHub Actions) | Jsonnet + envsubst + deploy |
| sing-box `users[]` | Billing bot | Прямая запись в config.json + restart |
| Client configs per user | Billing bot | Генерация JSON + отправка в Telegram |
| TLS certs, Caddy | CI/CD (GitHub Actions) | Deploy workflow |
| Infrastructure | Terraform | Servers, DNS, firewall |

## File Impact

| File | Action | Risk | Description |
|------|--------|------|-------------|
| `configs/vpn/hel-01/sing-box/config.json.tpl` | modify | medium | Перевести users на пустой массив, бот наполняет |
| `configs/vpn/hel-01/docker-compose.yaml` | modify | medium | Добавить billing-bot контейнер |
| `terraform/secrets.tf` | modify | low | Убрать per-server VLESS_UUID, HY2_PASSWORD из GitHub env (бот генерит сам) |
| `.github/workflows/_deploy-vpn.yml` | modify | medium | Убрать VLESS_UUID/HY2_PASSWORD из envsubst, добавить merge с users из бота |
| `services/billing-bot/` | create | — | Новый Python-сервис (бот) |
| `services/billing-bot/Dockerfile` | create | — | Docker-образ для бота |
| `services/billing-bot/bot/` | create | — | Код бота (aiogram 3) |
| `services/billing-bot/bot/models.py` | create | — | SQLAlchemy модели |
| `services/billing-bot/bot/config_gen.py` | create | — | Генерация sing-box конфигов |
| `services/billing-bot/bot/sing_box.py` | create | — | Управление sing-box (update users, restart) |
| `scripts/backup-headscale-s3.sh` | modify | low | Добавить backup SQLite бота |

## Steps

### Step 1: sing-box server config — multi-user foundation

Изменить `config.json.tpl`: секции `users` в inbounds должны быть пустым массивом или содержать placeholder. Бот будет мержить пользователей в рантайме.

**Подход:** серверный конфиг делится на две части:
- **Статическая** (template) — inbounds structure, routing, TLS. Управляется CI/CD
- **Динамическая** (users) — массив пользователей. Управляется ботом

Бот при старте и при каждом изменении пользователей:
1. Читает текущий `/etc/sing-box/config.json`
2. Обновляет массивы `users[]` в каждом inbound
3. Записывает обратно
4. Рестартит sing-box контейнер

- [ ] Изменить `config.json.tpl` — убрать `${VLESS_UUID}` и `${HY2_PASSWORD}` из users, оставить пустые массивы
- [ ] Обновить `_deploy-vpn.yml` — убрать VLESS_UUID и HY2_PASSWORD из envsubst env
- [ ] Обновить `terraform/secrets.tf` — убрать генерацию `random_uuid.vless` и `random_password.hy2` (или оставить для обратной совместимости и пометить deprecated)
- [ ] Validation: `docker compose config --quiet` проходит, sing-box стартует с пустым users (никто не подключится до добавления пользователей ботом)

### Step 2: Billing bot — project scaffold

Структура проекта:

```
services/billing-bot/
  Dockerfile
  pyproject.toml          # uv, dependencies
  bot/
    __init__.py
    __main__.py           # entrypoint
    config.py             # settings from env vars
    models.py             # SQLAlchemy models (User, Payment, Subscription)
    database.py           # async SQLite engine
    handlers/
      __init__.py
      admin.py            # /users, /approve, /suspend, /paid, /revenue
      user.py             # /start, /status, /config, /pay
    services/
      __init__.py
      credentials.py      # UUID/password generation
      config_gen.py       # sing-box client config generation
      sing_box.py         # server config update + container restart
      scheduler.py        # payment reminders cron
```

- [ ] Инициализировать Python-проект с uv: `pyproject.toml` с зависимостями (aiogram>=3.4, sqlalchemy>=2.0, aiosqlite, apscheduler>=3.10, docker>=7.0)
- [ ] Создать `Dockerfile` (python:3.12-slim, multi-stage build, non-root user)
- [ ] Создать `config.py` — загрузка настроек из env vars (BOT_TOKEN, ADMIN_TELEGRAM_ID, SING_BOX_CONFIG_PATH, etc.)
- [ ] Создать `__main__.py` — инициализация бота, подключение handlers, запуск scheduler
- [ ] Validation: `docker build` проходит, контейнер стартует и подключается к Telegram API

### Step 3: Database models

```python
class User:
    id: int (PK)
    telegram_id: int (unique)
    username: str (nullable)
    full_name: str
    vless_uuid: str (unique)         # generated at approve
    hy2_password: str (unique)       # generated at approve
    status: enum (pending/active/suspended/expired)
    platform: str (macos/ios/linux/android/windows)
    created_at: datetime
    approved_at: datetime (nullable)
    expires_at: datetime (nullable)  # subscription end date

class Payment:
    id: int (PK)
    user_id: FK -> User
    amount: int                      # в рублях
    payment_date: datetime
    confirmed_by: str                # admin who confirmed
    period_months: int (default 1)
    note: str (nullable)
```

- [ ] Создать `models.py` с SQLAlchemy 2.0 async models
- [ ] Создать `database.py` — async engine, session factory, init_db()
- [ ] Alembic не нужен для SQLite на 5-20 пользователей — `create_all()` при старте
- [ ] Validation: бот стартует, создаёт `data/billing.db` с таблицами

### Step 4: Bot handlers — admin commands

Бот различает admin и обычных пользователей по `ADMIN_TELEGRAM_ID`.

**Admin commands:**
- `/users` — таблица пользователей (имя, статус, дата оплаты, дата окончания)
- `/approve <telegram_id>` — одобрить pending-запрос, сгенерировать credentials, добавить в sing-box, отправить конфиг
- `/suspend <telegram_id>` — приостановить пользователя, убрать из sing-box
- `/paid <telegram_id> [amount] [months]` — подтвердить оплату, продлить подписку
- `/revenue` — сумма платежей за текущий/прошлый месяц

- [ ] Создать `handlers/admin.py` с middleware для проверки admin
- [ ] Реализовать CRUD-операции через SQLAlchemy async sessions
- [ ] Validation: команды работают в Telegram, данные сохраняются в SQLite

### Step 5: Bot handlers — user commands

**User commands:**
- `/start` — приветствие + запрос доступа. Пользователь выбирает платформу (inline keyboard). Admin получает уведомление с кнопками Approve/Reject
- `/status` — текущий статус подписки, дата оплаты, дней осталось
- `/config` — получить свой клиентский конфиг (файлом). Только для active пользователей
- `/pay` — реквизиты для оплаты (номер карты/телефона для СБП, сумма)

- [ ] Создать `handlers/user.py`
- [ ] Inline keyboard для выбора платформы при `/start`
- [ ] Inline keyboard для admin при новом запросе (Approve / Reject)
- [ ] Validation: полный flow — /start → admin approve → user получает конфиг

### Step 6: Credential generation & sing-box management

**Генерация credentials:**
- `vless_uuid` — `uuid.uuid4()`
- `hy2_password` — `secrets.token_urlsafe(32)`

**Обновление sing-box server config:**
1. Прочитать `/etc/sing-box/config.json`
2. Для каждого inbound типа `vless` — обновить `users[]` из активных пользователей в БД
3. Для каждого inbound типа `hysteria2` — аналогично с паролями
4. Записать обратно
5. `docker restart sing-box` через Docker SDK

**Генерация client config:**
- Шаблон на основе существующих `client-{platform}.jsonnet` → но без Jsonnet (бот генерит JSON напрямую из Python-шаблона)
- Подставить: user UUID, user HY2 password, SERVER_IPV4, REALITY_PUBLIC_KEY, REALITY_SHORT_ID
- SERVER_IPV4 и REALITY keys бот берёт из env vars (те же что в deploy)

- [ ] Создать `services/credentials.py` — генерация UUID и паролей
- [ ] Создать `services/sing_box.py` — чтение/обновление config.json, restart через Docker SDK
- [ ] Создать `services/config_gen.py` — per-user client config generation (JSON templates per platform)
- [ ] Validation: approve пользователя → sing-box config обновлён → `docker logs sing-box` без ошибок → клиентский конфиг подключается к VPN

### Step 7: Payment reminders & auto-suspend

APScheduler cron jobs:

| Job | Schedule | Action |
|-----|----------|--------|
| reminder_3d | ежедневно 10:00 | Пользователи с expires_at через 3 дня → напоминание |
| reminder_today | ежедневно 10:00 | Пользователи с expires_at сегодня → последнее предупреждение |
| auto_suspend | ежедневно 03:00 | Пользователи с expires_at + 3 дня grace → suspend + убрать из sing-box |

- [ ] Создать `services/scheduler.py` — APScheduler с AsyncIOScheduler
- [ ] Реализовать 3 cron-задачи
- [ ] При suspend — автоматически обновить sing-box config и restart
- [ ] Уведомить admin о каждом auto-suspend
- [ ] Validation: изменить expires_at тестового пользователя на завтра → получить напоминание

### Step 8: Docker integration & deployment

**docker-compose.yaml** — новый сервис:

```yaml
billing-bot:
  build: ../../services/billing-bot
  container_name: billing-bot
  restart: unless-stopped
  volumes:
    - billing_data:/app/data                    # SQLite
    - ./sing-box:/etc/sing-box                  # sing-box config (rw)
    - /var/run/docker.sock:/var/run/docker.sock:ro  # restart sing-box
  environment:
    - BOT_TOKEN=${BOT_TOKEN}
    - ADMIN_TELEGRAM_ID=${ADMIN_TELEGRAM_ID}
    - SERVER_IPV4=${SERVER_IPV4}
    - REALITY_PUBLIC_KEY=${REALITY_PUBLIC_KEY}
    - REALITY_SHORT_ID=${REALITY_SHORT_ID}
    - SALAMANDER_PASSWORD=${SALAMANDER_PASSWORD}
    - MONTHLY_PRICE=300
  depends_on:
    - sing-box
```

**Секреты**: BOT_TOKEN и ADMIN_TELEGRAM_ID добавить в Terraform → GitHub Actions environment secrets.

**Deploy workflow**: после `docker compose up` бот стартует и восстанавливает users в sing-box config из своей БД (идемпотентно).

**Backup**: добавить `billing_data` volume в существующий backup-скрипт.

- [ ] Обновить `configs/vpn/hel-01/docker-compose.yaml`
- [ ] Добавить `BOT_TOKEN`, `ADMIN_TELEGRAM_ID` в Terraform secrets
- [ ] Обновить `_deploy-vpn.yml` — добавить новые env vars в render step
- [ ] Обновить backup-скрипт — включить billing SQLite
- [ ] Добавить `services/billing-bot/` и `templates/sing-box/` в paths trigger для deploy
- [ ] Validation: `docker compose up -d` — все контейнеры running, бот отвечает в Telegram

### Step 9: Reconciliation at bot startup

При старте бота (и при каждом deploy, который пересоздаёт контейнеры):
1. Бот читает active users из SQLite
2. Генерирует полный sing-box config с актуальными users[]
3. Записывает в `/etc/sing-box/config.json`
4. Ждёт пока sing-box контейнер будет running
5. Готов к работе

Это гарантирует что после deploy (который перезаписывает config.json из шаблона с пустыми users) бот восстановит пользователей.

- [ ] Реализовать startup reconciliation в `__main__.py`
- [ ] Добавить health check для бота в docker-compose
- [ ] Validation: `docker compose up -d --force-recreate` → sing-box имеет правильных users через 10 секунд

## Risk Assessment

- **Overall risk**: MEDIUM
- **Blast radius**: VPN-доступ для всех пользователей (при ошибке в sing-box config update бот может сломать конфиг)
- **Mitigation**: бот делает backup config.json перед каждым обновлением; валидирует JSON перед записью; при ошибке — rollback из backup
- **Rollback**: убрать billing-bot из docker-compose, вернуть static users в config.json.tpl, задеплоить через CI/CD. Занимает 5 минут
- **Docker socket**: read-only mount, но бот может рестартить любой контейнер. Mitigation: бот только вызывает `docker restart sing-box`, никаких других операций

## Validation

Полный end-to-end тест после реализации:

- [ ] Друг пишет боту `/start` → выбирает платформу → admin получает запрос
- [ ] Admin нажимает Approve → друг получает конфиг файлом
- [ ] Друг импортирует конфиг в sing-box/Hiddify → VPN работает
- [ ] Admin: `/paid @friend 300 1` → подписка продлена на 1 месяц
- [ ] За 3 дня до конца → друг получает напоминание
- [ ] Просрочка +3 дня → друг автоматически отключён, VPN не работает
- [ ] Admin: `/paid @friend 300 1` → друг снова активен, получает конфиг
- [ ] `docker compose up -d --force-recreate` → бот восстанавливает users, VPN работает
