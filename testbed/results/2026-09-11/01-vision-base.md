# 01-vision-base

**Run:** 2026-09-11T19:34:19+00:00

## Config

| Field | Value |
|---|---|
| port | `11001` |
| network | `raw` |
| sni | `www.googletagmanager.com` |
| flow | `xtls-rprx-vision` |
| sockopt | `False` |
| xmux | `False` |
| testpre | `False` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000146 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 0.154348 |
| Total (1 KB) | 0.154416 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 296395891 | 2371.2 |
| DL max | 313998966 | 2512.0 |
| UL avg | 174643865 | 1397.2 |
| UL max | 176794017 | 1414.4 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=01-vision-base
timestamp=2026-09-11T19:34:19+00:00
handshake_raw=tcp=0.000146 tls=0.000000 ttfb=0.154348 total=0.154416 httpcode=200
dl_run_1=290655889
dl_run_2=284532820
dl_run_3=313998966
dl_avg_bytes_s=296395891
dl_max_bytes_s=313998966
dl_fails=0
ul_run_1=176794017
ul_run_2=175348153
ul_run_3=171789427
ul_avg_bytes_s=174643865
ul_max_bytes_s=176794017
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
