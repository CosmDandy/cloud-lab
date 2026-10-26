# 12-grpc-mm-sockopt

**Run:** 2026-09-11T19:37:17+00:00

## Config

| Field | Value |
|---|---|
| port | `11012` |
| network | `grpc` |
| sni | `update.googleapis.com` |
| service_name | `881935c7a421ec` |
| multi_mode | `True` |
| sockopt | `True` |
| xmux | `False` |
| testpre | `False` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000144 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 0.002055 |
| Total (1 KB) | 0.002248 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 262135001 | 2097.1 |
| DL max | 293755384 | 2350.0 |
| UL avg | 245187082 | 1961.5 |
| UL max | 258558279 | 2068.5 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=12-grpc-mm-sockopt
timestamp=2026-09-11T19:37:17+00:00
handshake_raw=tcp=0.000144 tls=0.000000 ttfb=0.002055 total=0.002248 httpcode=200
dl_run_1=203455485
dl_run_2=289194134
dl_run_3=293755384
dl_avg_bytes_s=262135001
dl_max_bytes_s=293755384
dl_fails=0
ul_run_1=227189080
ul_run_2=258558279
ul_run_3=249813888
ul_avg_bytes_s=245187082
ul_max_bytes_s=258558279
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
