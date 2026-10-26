# 08-xhttp-packet-xmux

**Run:** 2026-09-11T19:36:07+00:00

## Config

| Field | Value |
|---|---|
| port | `11008` |
| network | `xhttp` |
| sni | `www.swisscom.ch` |
| mode | `packet-up` |
| path | `/2562188470` |
| sockopt | `True` |
| xmux | `True` |
| testpre | `False` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000135 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 0.001733 |
| Total (1 KB) | 0.001788 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 174396741 | 1395.2 |
| DL max | 177951860 | 1423.6 |
| UL avg | 32025048 | 256.2 |
| UL max | 32035982 | 256.3 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=08-xhttp-packet-xmux
timestamp=2026-09-11T19:36:07+00:00
handshake_raw=tcp=0.000135 tls=0.000000 ttfb=0.001733 total=0.001788 httpcode=200
dl_run_1=173419245
dl_run_2=177951860
dl_run_3=171819118
dl_avg_bytes_s=174396741
dl_max_bytes_s=177951860
dl_fails=0
ul_run_1=32035982
ul_run_2=32026810
ul_run_3=32012354
ul_avg_bytes_s=32025048
ul_max_bytes_s=32035982
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
