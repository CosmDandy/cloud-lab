# 07-xhttp-packet-no

**Run:** 2026-09-11T19:35:48+00:00

## Config

| Field | Value |
|---|---|
| port | `11007` |
| network | `xhttp` |
| sni | `www.swisscom.ch` |
| mode | `packet-up` |
| path | `/9cd965cf69` |
| sockopt | `True` |
| xmux | `False` |
| testpre | `False` |

## Handshake

| Stage | Seconds |
|---|---|
| TCP connect | 0.000128 |
| TLS+Reality handshake | 0.000000 |
| TTFB | 0.116585 |
| Total (1 KB) | 0.116733 |
| HTTP code | 200 |

## Throughput

| | bytes/s | Mbit/s |
|---|---|---|
| DL avg | 174943053 | 1399.5 |
| DL max | 182771882 | 1462.2 |
| UL avg | 31609412 | 252.9 |
| UL max | 31966223 | 255.7 |

DL fails: 0 / UL fails: 0

## Connection-freezing probes

| Payload | Result |
|---|---|
| 5 KB | `ok` |
| 16 KB | `ok` |
| 50 KB | `ok` |

## Raw

```
variant=07-xhttp-packet-no
timestamp=2026-09-11T19:35:48+00:00
handshake_raw=tcp=0.000128 tls=0.000000 ttfb=0.116585 total=0.116733 httpcode=200
dl_run_1=165073018
dl_run_2=176984261
dl_run_3=182771882
dl_avg_bytes_s=174943053
dl_max_bytes_s=182771882
dl_fails=0
ul_run_1=31966223
ul_run_2=31410113
ul_run_3=31451901
ul_avg_bytes_s=31609412
ul_max_bytes_s=31966223
ul_fails=0
cf_meta={"origin":"local","note":"transport overhead bench, no external path"} 
freeze_5000=ok
freeze_16000=ok
freeze_50000=ok
```
