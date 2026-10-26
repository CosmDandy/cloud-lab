# 03-vision-testpre

**Run:** 2026-09-11T19:34:48+00:00

## Config

| Field | Value |
|---|---|
| port | `11003` |
| network | `raw` |
| sni | `www.googletagmanager.com` |
| flow | `xtls-rprx-vision` |
| sockopt | `False` |
| xmux | `False` |
| testpre | `True` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000125 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 0.137825 |
| Total (1 KB) | 0.137869 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 309466274 | 2475.7 |
| DL max | 316159922 | 2529.3 |
| UL avg | 175767593 | 1406.1 |
| UL max | 182640395 | 1461.1 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=03-vision-testpre
timestamp=2026-09-11T19:34:48+00:00
handshake_raw=tcp=0.000125 tls=0.000000 ttfb=0.137825 total=0.137869 httpcode=200
dl_run_1=309409376
dl_run_2=302829525
dl_run_3=316159922
dl_avg_bytes_s=309466274
dl_max_bytes_s=316159922
dl_fails=0
ul_run_1=172885352
ul_run_2=182640395
ul_run_3=171777033
ul_avg_bytes_s=175767593
ul_max_bytes_s=182640395
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
