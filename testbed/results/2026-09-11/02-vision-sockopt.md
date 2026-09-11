# 02-vision-sockopt

**Run:** 2026-09-11T19:34:34+00:00

## Config

| Field | Value |
|---|---|
| port | `11002` |
| network | `raw` |
| sni | `www.googletagmanager.com` |
| flow | `xtls-rprx-vision` |
| sockopt | `True` |
| xmux | `False` |
| testpre | `False` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000129 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 0.137546 |
| Total (1 KB) | 0.137590 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 294409406 | 2355.3 |
| DL max | 300654884 | 2405.2 |
| UL avg | 180257101 | 1442.1 |
| UL max | 182659077 | 1461.3 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=02-vision-sockopt
timestamp=2026-09-11T19:34:34+00:00
handshake_raw=tcp=0.000129 tls=0.000000 ttfb=0.137546 total=0.137590 httpcode=200
dl_run_1=294441262
dl_run_2=288132072
dl_run_3=300654884
dl_avg_bytes_s=294409406
dl_max_bytes_s=300654884
dl_fails=0
ul_run_1=182659077
ul_run_2=180297779
ul_run_3=177814447
ul_avg_bytes_s=180257101
ul_max_bytes_s=182659077
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
