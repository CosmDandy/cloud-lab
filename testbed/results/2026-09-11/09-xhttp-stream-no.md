# 09-xhttp-stream-no

**Run:** 2026-09-11T19:36:25+00:00

## Config

| Field | Value |
|---|---|
| port | `11009` |
| network | `xhttp` |
| sni | `www.swisscom.ch` |
| mode | `stream-up` |
| path | `/26399489cd` |
| sockopt | `True` |
| xmux | `False` |
| testpre | `False` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000140 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 4.680453 |
| Total (1 KB) | 4.680497 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 173130157 | 1385.0 |
| DL max | 180378914 | 1443.0 |
| UL avg | 187176649 | 1497.4 |
| UL max | 191311401 | 1530.5 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=09-xhttp-stream-no
timestamp=2026-09-11T19:36:25+00:00
handshake_raw=tcp=0.000140 tls=0.000000 ttfb=4.680453 total=4.680497 httpcode=200
dl_run_1=158663359
dl_run_2=180348200
dl_run_3=180378914
dl_avg_bytes_s=173130157
dl_max_bytes_s=180378914
dl_fails=0
ul_run_1=188051932
ul_run_2=191311401
ul_run_3=182166616
ul_avg_bytes_s=187176649
ul_max_bytes_s=191311401
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
