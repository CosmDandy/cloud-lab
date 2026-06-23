# 01-vision-base

**Run:** 2026-06-22T19:58:24+00:00

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
| TCP connect | 0.000204 |
| TLS+Reality handshake | 0.131466 |
| TTFB | 0.191305 |
| Total (1 KB) | 0.191418 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 7 | 0.0 |
| DL max | 7 | 0.0 |
| UL avg | — | 0.0 |
| UL max | — | 0.0 |

DL fails: 0 / UL fails: 3

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `fail` |

## Raw

```
bash: warning: setlocale: LC_ALL: cannot change locale (en_US.UTF-8)
variant=01-vision-base
timestamp=2026-06-22T19:58:24+00:00
handshake_raw=tcp=0.000204 tls=0.131466 ttfb=0.191305 total=0.191418 httpcode=200
dl_run_1=7
dl_run_2=7
dl_run_3=7
dl_avg_bytes_s=7
dl_max_bytes_s=7
dl_fails=0
ul_fails=3
cf_meta={} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=fail
```
