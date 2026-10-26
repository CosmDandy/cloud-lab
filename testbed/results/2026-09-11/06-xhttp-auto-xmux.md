# 06-xhttp-auto-xmux

**Run:** 2026-09-11T19:35:33+00:00

## Config

| Field | Value |
|---|---|
| port | `11006` |
| network | `xhttp` |
| sni | `www.swisscom.ch` |
| mode | `auto` |
| path | `/e68c47d852` |
| sockopt | `True` |
| xmux | `True` |
| testpre | `False` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000133 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 0.001773 |
| Total (1 KB) | 0.001897 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 182031594 | 1456.3 |
| DL max | 187188554 | 1497.5 |
| UL avg | 183441059 | 1467.5 |
| UL max | 189243404 | 1513.9 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=06-xhttp-auto-xmux
timestamp=2026-09-11T19:35:33+00:00
handshake_raw=tcp=0.000133 tls=0.000000 ttfb=0.001773 total=0.001897 httpcode=200
dl_run_1=187188554
dl_run_2=179123120
dl_run_3=179783110
dl_avg_bytes_s=182031594
dl_max_bytes_s=187188554
dl_fails=0
ul_run_1=187890812
ul_run_2=173188963
ul_run_3=189243404
ul_avg_bytes_s=183441059
ul_max_bytes_s=189243404
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
