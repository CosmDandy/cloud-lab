# 10-xhttp-stream-xmux

**Run:** 2026-09-11T19:36:46+00:00

## Config

| Field | Value |
|---|---|
| port | `11010` |
| network | `xhttp` |
| sni | `www.swisscom.ch` |
| mode | `stream-up` |
| path | `/c4ed72cb6a` |
| sockopt | `True` |
| xmux | `True` |
| testpre | `False` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000129 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 0.001734 |
| Total (1 KB) | 0.001773 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 173346413 | 1386.8 |
| DL max | 177551858 | 1420.4 |
| UL avg | 191894703 | 1535.2 |
| UL max | 195406386 | 1563.3 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=10-xhttp-stream-xmux
timestamp=2026-09-11T19:36:46+00:00
handshake_raw=tcp=0.000129 tls=0.000000 ttfb=0.001734 total=0.001773 httpcode=200
dl_run_1=174109465
dl_run_2=177551858
dl_run_3=168377916
dl_avg_bytes_s=173346413
dl_max_bytes_s=177551858
dl_fails=0
ul_run_1=186167043
ul_run_2=195406386
ul_run_3=194110681
ul_avg_bytes_s=191894703
ul_max_bytes_s=195406386
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
