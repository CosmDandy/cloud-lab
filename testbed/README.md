# VPN testbed

Изолированный сравнительный бенчмарк Xray-конфигов на LXC в локальной сети РФ. Стандартный flow для любого нового inbound'а до промоута в прод.

## Зачем

Прод-тесты через клиента (Happ) — субъективны: "вроде быстрее" / "вроде латенция выросла". Здесь — точные метрики на одном железе одновременно:

- TCP/TLS handshake time
- DL/UL throughput через `speed.cloudflare.com`
- TTFB
- CPU peak per config
- Behavior на connection-freezing-style нагрузке

## Архитектура

```
LXC vpn-testbed (10.0.1.165) на pve-local-l-01:
  Docker:
    xray-srv  — одиночный xray-server, поочерёдно меняется конфиг
    xray-cli  — одиночный xray-client → SOCKS5 на localhost:10808
  bench/run-all.sh — главный looper:
    for each server-configs/NN-name/:
      1. Запустить xray-srv с config.json
      2. Сгенерировать client/config.json под текущий transport
      3. Запустить xray-cli (SOCKS5)
      4. Прогнать benchmark.sh через --proxy socks5h://localhost:10808
      5. Сохранить results/<DATE>/NN-name.md
      6. Остановить контейнеры
    Сгенерировать SUMMARY.md
```

Канал RU-аплинка — 100 Мбит, тесты прогоняются **последовательно**.

## Конфиги под сравнение (12)

| # | Tag | Transport | Mode | xmux | sockopt | testpre | multiMode | dest/SNI |
|---|---|---|---|---|---|---|---|---|
| 01 | vision-base | raw TCP | — | — | ✗ | ✗ | — | googletagmanager |
| 02 | vision-sockopt | raw TCP | — | — | ✓ | ✗ | — | googletagmanager |
| 03 | vision-testpre | raw TCP | — | — | ✗ | ✓ | — | googletagmanager |
| 04 | vision-full | raw TCP | — | — | ✓ | ✓ | — | googletagmanager |
| 05 | xhttp-auto-no | xhttp | auto | ✗ | ✓ | — | — | swisscom |
| 06 | xhttp-auto-xmux | xhttp | auto | ✓ | ✓ | — | — | swisscom |
| 07 | xhttp-packet-no | xhttp | packet-up | ✗ | ✓ | — | — | swisscom |
| 08 | xhttp-packet-xmux | xhttp | packet-up | ✓ | ✓ | — | — | swisscom |
| 09 | xhttp-stream-no | xhttp | stream-up | ✗ | ✓ | — | — | swisscom |
| 10 | xhttp-stream-xmux | xhttp | stream-up | ✓ | ✓ | — | — | swisscom |
| 11 | grpc-base | grpc | — | — | ✗ | — | ✗ | update.googleapis.com |
| 12 | grpc-mm-sockopt | grpc | — | — | ✓ | — | ✓ | update.googleapis.com |

## Usage

```bash
# На dev-машине, после правки configs/script:
rsync -a --delete testbed/ root@10.0.1.165:/root/testbed/

# На LXC:
ssh root@10.0.1.165
cd /root/testbed
./bench/run-all.sh

# Результаты — на dev:
rsync -a root@10.0.1.165:/root/testbed/results/ testbed/results/
```

## Flow для добавления нового inbound в прод

**Stop using "сразу в прод и щупаем Happ"**. Новый паттерн:

1. **Описать** новый inbound (transport+флаги+SNI) — внутри `testbed/server-configs/NN-name/config.json`
2. **Прогнать** `./bench/run-all.sh` (или конкретный конфиг) на LXC
3. **Открыть** `results/<DATE>/NN-name.md` — сравнить с baseline и предыдущими тестами
4. **Решение**: если метрики не хуже baseline и есть прирост — промоут в прод config-profile RemnaWave
5. **После промоута** — повторный тест на прод-ноде (отдельный inbound на тестовом порту), сравнить с testbed

Этот flow зафиксирован в memory как [project_testbed_flow](../../home/vscode/.claude/projects/-workspaces-local-cloud-lab-main/memory/project_testbed_flow.md) — Claude должен следовать ему при любых изменениях inbound параметров.

## Reality keys для testbed

Ключи **не коммитятся** (см. `.gitignore`). Сгенерировать свои и положить в `.env`:

```bash
# приватный + публичный ключ Reality
docker run --rm ghcr.io/xtls/xray-core:latest x25519
# UUID тестового юзера
docker run --rm ghcr.io/xtls/xray-core:latest uuid
```

Затем заполнить `.env` (скопировать из `.env.example`):
```
REALITY_PRIVATE_KEY=<из x25519 PrivateKey>
REALITY_PUBLIC_KEY=<из x25519 Password/PublicKey>
CLIENT_UUID=<из uuid>
```

`generate-configs.py` читает ключ из env. Сгенерированные `server-configs/*/config.json`
и `dist/` содержат ключ → они в `.gitignore`, в репо не попадают.
Это **testbed-only** идентичность, отдельная от прода — не использовать в проде.
