# VPN Platform Evolution Plan

## Context

Текущая инфраструктура (sing-box на одном Hetzner-сервере) сталкивается с ограничениями:
- ТСПУ блокирует VLESS+Vision+TCP, нет XHTTP транспорта (самого устойчивого)
- Один провайдер (Hetzner) — IP-диапазоны активно блокируют
- Клиентский конфиг знает только один сервер — нет failover между серверами
- Конфиги копируются вручную для каждого сервера
- Нет subscription URL для автообновления на клиентах

Цель: превратить проект в расширяемую платформу с мульти-провайдером, мульти-движком и автоматической балансировкой.

---

## Фаза 0: Git-стратегия

**Тег `v1.0.0`** на текущий master как точку отката. Feature branches для каждой фазы.

---

## Фаза 1: Xray-core engine

### Зачем
Xray-core поддерживает **fallbacks** (3 протокола на одном порту 443) и **XHTTP** транспорт (спроектирован против connection freezing ТСПУ). sing-box ни то, ни другое не умеет.

### Что делаем

**Создаём:**
- `templates/engines/xray-core/server-config.json.tpl` — конфиг Xray с fallbacks:
  - VLESS+Reality+Vision на :443 (главный, TCP)
  - VLESS+gRPC через fallback (ALPN h2, serviceName "grpc")
  - VLESS+XHTTP через fallback (path "/xhttp")
- `templates/engines/xray-core/docker-compose.fragment.yaml` — xray сервис
- `templates/engines/sing-box/server-config.json.tpl` — перенос из `configs/vpn/hel-01/sing-box/config.json.tpl`
- `templates/engines/sing-box/docker-compose.fragment.yaml` — sing-box сервис

**Изменяем:**
- `terraform/variables.tf` — поле `engine = optional(string, "sing-box")` в vpn_servers
- `templates/sing-box/lib/outbounds.libsonnet` — добавить `vlessRealityXhttp()` outbound

**Hysteria2 и Xray:** Xray не поддерживает Hysteria2. На Xray-серверах доступны 3 VLESS-транспорта (Vision, gRPC, XHTTP). Hysteria2 остаётся на sing-box серверах.

**Совместимость XHTTP с клиентами:**
- sing-box клиент **не поддерживает** XHTTP нативно
- XHTTP доступен через клиенты с Xray-ядром: Hiddify, v2rayN, v2rayNG, NekoBox
- В sing-box клиентских конфигах XHTTP не включаем; в V2Ray share links — включаем

### Целевая конфигурация Xray-сервера
```
:443/tcp → Xray fallbacks
  ├── VLESS+Reality+Vision (прямой TLS)
  ├── VLESS+gRPC (ALPN h2)
  └── VLESS+XHTTP (path /xhttp)
:8443/tcp → Caddy (раздача конфигов)
```

---

## Фаза 2: Мульти-провайдер Terraform

### Зачем
IP-диапазоны Hetzner блокируют. Нужны серверы у провайдеров, чьи IP не в блоклистах.

### Провайдеры

| Провайдер | Цена | Terraform provider | Преимущество |
|---|---|---|---|
| **Oracle Cloud** | **Бесплатно** (ARM 4CPU/24GB) | `hashicorp/oci` | Free Tier навсегда, IP не блокируют |
| **Vultr** | $2.5/мес | `vultr/vultr` | Дёшево, много локаций |
| **Scaleway** | ~€3/мес | `scaleway/scaleway` | Европейские IP |

Приоритет: **Oracle Cloud Free Tier** (бесплатно + незаблокированные IP).

### Что делаем

**Создаём:**
- `terraform/modules/oci-server/` — модуль Oracle Cloud (instance + VCN + subnet + security list + Cloudflare DNS)
- `terraform/cloud-init/vpn-oci.yaml.tftpl` — cloud-init для OCI (или унифицировать с vpn.yaml.tftpl)

**Изменяем:**
- `terraform/main.tf` — роутинг по `provider`: `for_each = { for k, v in var.vpn_servers : k => v if v.provider == "oci" }`
- `terraform/variables.tf` — поле `provider`, OCI credentials
- `terraform/versions.tf` — добавить provider `hashicorp/oci`
- `terraform/secrets.tf` — GH environments для OCI серверов
- `terraform/terraform.tfvars` — новый сервер `oci-01`

**Единый интерфейс outputs всех модулей:** `ipv4_address`, `fqdn`, `name`

---

## Фаза 3: Мульти-серверные клиентские конфиги

### Зачем
Сейчас клиент знает один сервер. Если его заблокируют — ручная перенастройка. Нужен автоматический failover между серверами.

### Архитектура outbounds

```
proxy (selector — ручной выбор)
  ├── auto (urltest между серверами)
  │   ├── auto-hel-01 (urltest протоколов hel-01)
  │   │   ├── vless-vision-hel-01
  │   │   ├── vless-grpc-hel-01
  │   │   └── hy2-hel-01
  │   └── auto-oci-01 (urltest протоколов oci-01)
  │       ├── vless-vision-oci-01
  │       ├── vless-grpc-oci-01
  │       └── vless-xhttp-oci-01
  ├── auto-hel-01 (прямой выбор сервера)
  ├── auto-oci-01
  └── direct
```

### Что делаем

**Рефакторинг `outbounds.libsonnet`:**
- Функции принимают server object: `vlessRealityVision(server)` вместо хардкоженного `${SERVER_IPV4}`
- `serverOutbounds(server)` — протоколы по engine (sing-box: Vision+gRPC+Hy2, xray: Vision+gRPC+XHTTP)
- `allServersOutbounds(servers)` — все протоколы всех серверов
- `serverUrltest(server)` — urltest протоколов одного сервера
- `globalUrltest(servers)` — urltest между серверами
- `globalSelector(servers)` — selector для ручного выбора

**Рефакторинг `route.libsonnet`:**
- `serverDirectRules(servers)` — IP всех серверов → direct (предотвращение loop)

**Перенос клиентских конфигов:**
- `configs/vpn/hel-01/sing-box/client-*.jsonnet` → `templates/sing-box/client/*.jsonnet`
- Jsonnet получает серверы через `std.extVar('servers')` (JSON массив)

**CI pipeline:**
- Новый шаг: генерация `servers.json` из Terraform output + GH environments
- `jsonnet --ext-str servers="$(cat servers.json)"` при компиляции
- Клиентские конфиги деплоятся на ВСЕ серверы (каждый раздаёт полный набор)

### Ключевые файлы
- `templates/sing-box/lib/outbounds.libsonnet` — центральный рефакторинг
- `templates/sing-box/client/{base,linux,mobile,server}.jsonnet` — новые клиентские шаблоны
- `scripts/generate-servers-json.sh` — сбор данных серверов
- `.github/workflows/_deploy-vpn.yml` — мульти-серверная генерация

---

## Фаза 4: Subscription URL

### Зачем
При добавлении сервера клиенты должны получать обновлённые конфиги автоматически.

### Два формата подписки

| Формат | URL | Клиенты |
|---|---|---|
| sing-box JSON | `/sing-box/client-{platform}.json` | SFI, SFA, sing-box CLI |
| V2Ray base64 | `/subscribe` | Hiddify, v2rayN, v2rayNG, NekoBox |

### Что делаем
- Расширить `Caddyfile.tpl`: `/sing-box/*` + `/subscribe`
- Создать `scripts/generate-share-links.py` — генерация V2Ray share links (base64)
- Добавить шаг в CI workflow

---

## Фаза 5: Оркестрация и балансировка

### Как это работает в больших системах

VPN не поддаётся традиционному LB (reverse proxy, DNS round-robin), потому что:
- Клиент подключается по IP напрямую (Reality handshake)
- Нельзя поставить прокси перед VPN-сервером

**Решения:**

| Механизм | Как работает | Для нас |
|---|---|---|
| **Client-side urltest** | Клиент тестирует все серверы, выбирает лучший | Основной (Фаза 3) |
| **Subscription URL** | При добавлении сервера конфиги обновляются | Автоматизация (Фаза 4) |
| **CDN-fronted fallback** | VLESS+WS через Cloudflare (домен вместо IP) | Аварийный вариант |
| **Anycast** | Один IP, роутинг BGP | Нереалистично для личного проекта |

### CDN-fronted аварийный вариант
- Cloudflare-проксированный домен (`cdn-vpn.cosmdandy.dev`, `proxied = true`)
- VLESS+WebSocket через Cloudflare → origin сервер
- Ограничение: Cloudflare throttling 16KB в России
- Добавляется как последний outbound в urltest

### Динамическое расширение
Добавление сервера: tfvars → terraform apply → CI deploy → subscription обновляется → клиенты переключаются автоматически. ~15 минут от решения до работающего сервера.

---

## Кросс-платформенные клиенты

### Рекомендация

| Платформа | Основной | Альтернатива | Subscription |
|---|---|---|---|
| **Linux** | sing-box CLI | — | sing-box JSON |
| **macOS** | Hiddify | SFI (sing-box) | V2Ray base64 / sing-box JSON |
| **iOS** | Hiddify | SFI (sing-box) | V2Ray base64 / sing-box JSON |
| **Android** | Hiddify | SFA (sing-box) | V2Ray base64 / sing-box JSON |
| **Windows** | Hiddify | v2rayN | V2Ray base64 |

**Hiddify** — лучший выбор для всех GUI-платформ:
- Все 5 платформ (macOS, iOS, Android, Windows, Linux)
- Поддерживает sing-box И Xray ядра (можно переключать)
- Subscription URLs с автообновлением
- VLESS+Reality, Hysteria2, gRPC, **XHTTP** (через Xray ядро)
- Популярен в российском сообществе, активно развивается

**sing-box SFI/SFA** — для тех, кто предпочитает нативное:
- macOS + iOS (SFI), Android (SFA)
- Remote profile (subscription) поддерживается
- Нет XHTTP, но Vision + gRPC + Hysteria2 работают
- Нет Windows GUI

**v2rayN** — для Windows power users:
- Xray ядро, поддержка XHTTP
- Subscription URLs

**Для Linux CLI** — sing-box остаётся лучшим: TUN mode, systemd, urltest, полная автоматизация.

---

## Порядок и зависимости

```
Фаза 0 (30 мин)     → git tag v1.0.0
  ↓
Фаза 1 (4-6ч)       → Xray-core engine     ─┐
Фаза 2 (6-8ч)       → Мульти-провайдер      ─┤ параллельно
  ↓                                            ↓
Фаза 3 (8-12ч)      → Мульти-серверные конфиги (зависит от 1+2)
  ↓
Фаза 4 (3-4ч)       → Subscription URL
  ↓
Фаза 5 (2-3ч)       → CDN fallback + оркестрация
```

---

## Verification

1. **Фаза 1:** Задеплоить Xray на тестовый сервер, подключиться sing-box клиентом через Vision и gRPC, Hiddify через XHTTP. Проверить fallbacks: curl без auth → microsoft.com
2. **Фаза 2:** `terraform plan` без ошибок, `terraform apply` создаёт OCI сервер, DNS резолвится, CI деплоит
3. **Фаза 3:** Клиентский конфиг содержит outbounds всех серверов, urltest переключает при недоступности одного
4. **Фаза 4:** Subscription URL возвращает актуальный конфиг, Hiddify импортирует и видит все серверы
5. **Фаза 5:** При блокировке всех direct-IP серверов CDN fallback работает
