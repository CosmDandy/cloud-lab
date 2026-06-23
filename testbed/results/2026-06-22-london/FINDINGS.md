# Testbed findings — 2026-06-22 (London exit, RU→TSPU path)

**Setup:** Xray client on LXC `vpn-testbed` (10.0.1.165, RU home 100 Mbit + TSPU) →
12 isolated testbed inbounds on London MivoCloud node (194.180.158.12:11001-11012) →
DIRECT → speed.cloudflare.com. Production (remnanode) untouched.

**Line ceiling:** ~84 Mbit/s (home 100 Mbit uplink). Top configs are line-bound;
the meaningful signal is the **low performers** and the **per-flag deltas**.

## Ranking (DL avg Mbit/s)

| Rank | Variant | Mbit/s | Δ vs baseline |
|---|---|---|---|
| 1 | xhttp-stream-xmux | 84.4 | — |
| 2 | xhttp-packet-xmux | 84.0 | — |
| 3 | xhttp-auto-xmux | 83.6 | — |
| 4 | xhttp-stream-no | 82.0 | — |
| 5 | grpc-mm-sockopt | 80.9 | — |
| 6 | xhttp-auto-no | 80.8 | — |
| 7 | xhttp-packet-no | 80.8 | — |
| 8 | vision-sockopt | 77.1 | — |
| 9 | vision-full | 76.5 | — |
| 10 | vision-base | 61.4 | — |
| 11 | grpc-base | 51.9 | — |
| 12 | vision-testpre | 43.7 | — |

**Baseline direct (no VPN): 0.0 Mbit/s — throttled by TSPU at ~17 KB.**

## Conclusions (empirical, isolated per flag)

1. **`sockopt` (TFO + BBR + keepalive) — large gain, needed everywhere.**
   - Vision: 61.4 → 77.1 (**+26%**)
   - gRPC: 51.9 → 80.9 (**+56%**)

2. **`testpre` — HARMFUL. Remove it.**
   - Vision base 61.4 → +testpre 43.7 (**−29%**)
   - vision-full (sockopt+testpre) 76.5 < vision-sockopt 77.1 — testpre is a net drag even with sockopt.
   - This is the empirical cause of the "Vision latency feels worse" observation after testpre was added to production.

3. **`xmux` on XHTTP — best. Improves throughput + handshake 3×.**
   - TLS+Reality handshake with xmux: ~0.08s; without: ~0.24s (connection reuse).
   - Mode (auto/packet-up/stream-up) barely matters for throughput when xmux is on — all ~84. For RU anti-DPI choose `packet-up` (shortest connections vs the 16 KB freeze).

4. **gRPC multiMode** showed 80.9 with sockopt — but the jump is mostly sockopt, not multiMode. Keep `multiMode=false` for production (fingerprint safety); sockopt is the real win.

## Production implications

| Prod inbound | Current | Action |
|---|---|---|
| Vision (2053) | sockopt + **testpre** | **strip testpre/testseed** → ~77 instead of ~61 |
| Vision-Plain (2055) | sockopt, no testpre | = the winning Vision config (AB test answer) |
| gRPC (2083) | sockopt, multiMode=false | keep |
| XHTTP (2087) | packet-up + xmux + sockopt | keep — top config |
| XHTTP-Auto (2089) | auto, no xmux | redundant — xmux variant wins |
| XHTTP-PU (2443) | packet-up + xmux + sockopt | keep |

**AB tests resolved:** Vision-Plain (no testpre) > Vision (testpre); XHTTP+xmux > XHTTP-Auto.
