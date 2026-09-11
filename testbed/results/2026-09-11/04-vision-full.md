# 04-vision-full

**Run:** 2026-09-11T19:35:03+00:00

## Config

| Field | Value |
|---|---|
| port | `11004` |
| network | `raw` |
| sni | `www.googletagmanager.com` |
| flow | `xtls-rprx-vision` |
| sockopt | `True` |
| xmux | `False` |
| testpre | `True` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000128 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 0.151045 |
| Total (1 KB) | 0.151088 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 286793495 | 2294.3 |
| DL max | 312098947 | 2496.8 |
| UL avg | 179032823 | 1432.3 |
| UL max | 187246982 | 1498.0 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=04-vision-full
timestamp=2026-09-11T19:35:03+00:00
handshake_raw=tcp=0.000128 tls=0.000000 ttfb=0.151045 total=0.151088 httpcode=200
dl_run_1=236745899
dl_run_2=311535639
dl_run_3=312098947
dl_avg_bytes_s=286793495
dl_max_bytes_s=312098947
dl_fails=0
ul_run_1=187246982
ul_run_2=169828303
ul_run_3=180023186
ul_avg_bytes_s=179032823
ul_max_bytes_s=187246982
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
