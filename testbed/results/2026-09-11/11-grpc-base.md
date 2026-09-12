# 11-grpc-base

**Run:** 2026-09-11T19:37:02+00:00

## Config

| Field | Value |
|---|---|
| port | `11011` |
| network | `grpc` |
| sni | `update.googleapis.com` |
| service_name | `f94da231999102` |
| multi_mode | `False` |
| sockopt | `False` |
| xmux | `False` |
| testpre | `False` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000130 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 0.001682 |
| Total (1 KB) | 0.001718 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 226138347 | 1809.1 |
| DL max | 233888774 | 1871.1 |
| UL avg | 221196096 | 1769.6 |
| UL max | 242074481 | 1936.6 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=11-grpc-base
timestamp=2026-09-11T19:37:02+00:00
handshake_raw=tcp=0.000130 tls=0.000000 ttfb=0.001682 total=0.001718 httpcode=200
dl_run_1=216286190
dl_run_2=228240077
dl_run_3=233888774
dl_avg_bytes_s=226138347
dl_max_bytes_s=233888774
dl_fails=0
ul_run_1=190338421
ul_run_2=231175388
ul_run_3=242074481
ul_avg_bytes_s=221196096
ul_max_bytes_s=242074481
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
