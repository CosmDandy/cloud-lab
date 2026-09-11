# 05-xhttp-auto-no

**Run:** 2026-09-11T19:35:18+00:00

## Config

| Field | Value |
|---|---|
| port | `11005` |
| network | `xhttp` |
| sni | `www.swisscom.ch` |
| mode | `auto` |
| path | `/80074179df` |
| sockopt | `True` |
| xmux | `False` |
| testpre | `False` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000144 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 0.107240 |
| Total (1 KB) | 0.107288 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 171245809 | 1370.0 |
| DL max | 179290652 | 1434.3 |
| UL avg | 178367361 | 1426.9 |
| UL max | 180349155 | 1442.8 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=05-xhttp-auto-no
timestamp=2026-09-11T19:35:18+00:00
handshake_raw=tcp=0.000144 tls=0.000000 ttfb=0.107240 total=0.107288 httpcode=200
dl_run_1=165300064
dl_run_2=169146713
dl_run_3=179290652
dl_avg_bytes_s=171245809
dl_max_bytes_s=179290652
dl_fails=0
ul_run_1=175326018
ul_run_2=180349155
ul_run_3=179426910
ul_avg_bytes_s=178367361
ul_max_bytes_s=180349155
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
