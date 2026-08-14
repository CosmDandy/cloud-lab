# DPI-resistant self-hosted proxy solutions for Russia in 2026

**VLESS+Reality via Xray-core or sing-box remains the most effective protocol against Russian TSPU as of February 2026, but it now requires XHTTP or gRPC transport** — the simpler TCP+TLS variant was specifically targeted on February 17, 2026, with dramatic blocking escalation across many regions. Hysteria 2 (QUIC-based) serves as the strongest secondary protocol due to TSPU's primary focus on TCP traffic. For your Headscale+Tailscale mesh, sing-box in TUN mode is the recommended integration layer: it transparently captures WireGuard packets and routes them through DPI-resistant outbounds with automatic failover between protocols. The Russian censorship landscape now changes weekly, making multi-protocol agility the single most important architectural property of any solution you deploy.

Russia's TSPU infrastructure — installed at every ISP node nationwide — uses protocol fingerprinting, statistical traffic analysis, active probing, TLS fingerprinting, connection freezing, and SNI whitelisting. The government allocated **60 billion rubles (~$700M)** for TSPU upgrades through 2030, plus **2.27 billion rubles** specifically for AI-powered traffic classification. OpenVPN, WireGuard, IKEv2, L2TP, and PPTP are **100% blocked**. Shadowsocks is **~95% detected**, Trojan **~90%**, and VMess **~80%**. Approximately 41% of Russian internet users now rely on VPNs despite the crackdowns.

---

## TSPU's evolving detection arsenal demands constant adaptation

The TSPU system has evolved far beyond simple signature matching. Understanding its current capabilities is essential to choosing the right protocol stack.

**Connection freezing** (deployed June 2025) is the most impactful new technique: when a client connects via TLS 1.3 to a "suspicious" foreign IP (datacenter ASNs like Hetzner, DigitalOcean), the connection silently freezes after **~15-20KB** of transferred data. No RST packet — traffic simply stops flowing. This affects all TLS traffic to flagged IPs, not just VPN traffic. The Xray team responded with the **XHTTP transport**, which fragments responses across multiple short-lived TCP connections to stay under the threshold.

**Active probing** remains TSPU's most powerful weapon. When suspicious traffic is detected to an IP:port, TSPU connects from its own infrastructure, sends protocol-appropriate handshakes, and analyzes the server response. This technique defeated Trojan (~90% detection since August 2025) because Trojan servers respond distinctively to invalid requests. VLESS+Reality resists this because unauthenticated connections are transparently forwarded to the real target website — probers interact with genuine TLS from microsoft.com or whichever SNI you configure.

**TLS connection policing** started in November 2025 on Moscow home ISPs (MTS/MGTS): VLESS+Reality+Vision connections are disrupted once actual data starts flowing. The workaround involves removing the `xtls-rprx-vision` flow and applying multiplexing, though effectiveness varies by region. The **Aparecium** proof-of-concept demonstrated that both Reality and ShadowTLS v3 fail to relay TLS 1.3 NewSessionTicket post-handshake messages, creating a detectable discrepancy. Whether TSPU has deployed this detection in production is unknown but plausible.

**Cloudflare throttling** (June 2025) limits data to the first **16KB** per request to Cloudflare-protected sites across all major ISPs. This disrupted CDN-fronted proxy configurations and thousands of legitimate websites. **QUIC/HTTP/3** to foreign destinations is blocked on major ISPs; domestic QUIC (VK, Yandex) still works. ECH (Encrypted Client Hello) connections are blocked since November 2024.

| Detection method | Targeted protocols | Deployed since |
|---|---|---|
| Protocol fingerprinting | OpenVPN, WireGuard, IKEv2, PPTP, L2TP | 2023 |
| Statistical/behavioral analysis | Shadowsocks (random byte entropy) | 2024 |
| Active probing | Trojan, VMess, older Shadowsocks | Aug 2025 |
| TCP connection freezing (15-20KB) | All TLS to datacenter IPs | Jun 2025 |
| TLS connection policing | VLESS+Reality+Vision | Nov 2025 |
| SNI whitelisting | All TLS traffic during shutdowns | 2025 |
| QUIC blocking (international) | Hysteria 2, TUIC, HTTP/3 | 2024-2025 |

---

## Xray-core with VLESS+Reality: the frontline protocol

Xray-core (**35k+ GitHub stars**, latest release v1.260206.0 on February 10, 2026) is the most actively developed censorship circumvention tool and the origin of the VLESS+Reality protocol combination that currently leads in DPI resistance.

**How Reality works**: The server impersonates a legitimate website (e.g., `microsoft.com`) during the TLS 1.3 handshake. It relays the real site's ServerHello, so the DPI system sees a valid TLS handshake with a genuine SNI and certificate chain. Client authentication happens via X25519 key exchange embedded in the encrypted portion of the TLS session, invisible to observers. Unauthenticated connections (including active probes) are forwarded to the real target website. The **Vision flow control** (`xtls-rprx-vision`) eliminates TLS-in-TLS double encryption by detecting inner TLS traffic and using kernel-level `splice(2)` on Linux — this both improves performance and removes a detectable traffic pattern.

**Current Russia status (February 2026)**: VLESS+Reality with basic TCP+TLS transport was dramatically targeted on Feb 17, 2026. The working configurations now require:

- **XHTTP transport** (Xray's newest transport, designed specifically to counter connection freezing by using multiple short-lived HTTP connections)
- **gRPC transport** as an alternative to XHTTP
- **CDN-fronted setups** (VLESS+WebSocket through Cloudflare, though Cloudflare throttling limits this)
- Keeping Xray-core updated to ≥25.12.8 to avoid detection by Aparecium (which analyzes NewSessionTicket messages)
- Selecting SNI domains from Russian government whitelists (e.g., `vkvideo.ru` has been reported as a working Reality destination)

**Protocols supported**: VLESS (flagship), VMess (deprecated), Trojan, Shadowsocks (AEAD + 2022), SOCKS, HTTP, WireGuard (outbound), plus transports: TCP, WebSocket (deprecated in favor of XHTTP), gRPC, HTTP/2, QUIC, mKCP, XHTTP (H2 & H3). Post-quantum protection via ML-DSA-65 is available for forward-looking deployments.

**Clients for all platforms**: v2rayN (Windows/macOS/Linux, **76k stars**), v2rayNG (Android, **39k stars**), Shadowrocket and Streisand (iOS), Hiddify (all platforms), Nekoray (Linux/macOS/Windows). All support VLESS+Reality.

**Performance**: XTLS Vision achieves near-native TLS speed by eliminating redundant encryption. When proxying TLS 1.3 traffic with Splice active on Linux, the kernel handles data forwarding with near-zero CPU overhead. Benchmarks show Reality can increase effective throughput **~1.5x** over non-proxied connections in some configurations.

**Management**: JSON configuration (complex but powerful). Web panels include **3x-ui** (most popular, but criticized by the XTLS project for defaulting to plain HTTP), **Remnawave**, and **Hiddify**. The XTLS project recommends HTTPS-only panels.

---

## sing-box: the universal proxy platform and ideal integration layer

sing-box (**~22k+ stars**, latest v1.13.x) is the recommended client-side platform for your use case because it supports every relevant protocol, runs on all platforms, and its TUN mode can transparently capture Tailscale/WireGuard traffic.

**Protocol coverage is unmatched**: VLESS (with Reality), VMess, Trojan, Shadowsocks (including 2022 ciphers), Hysteria, Hysteria 2, TUIC v5, NaiveProxy (using Chromium's actual network stack), ShadowTLS v1/v2/v3, AnyTLS, WireGuard, Tor, SSH — **20+ protocols** with transports including TCP, WebSocket, QUIC, gRPC, HTTP/2, HTTPUpgrade. No other single tool covers this breadth.

**TUN mode** creates a virtual network interface that captures **all system traffic at Layer 3**, including WireGuard packets from Tailscale. This is the cleanest integration path for your Headscale mesh:

```
Tailscale WireGuard packets → sing-box TUN interface → L3→L4 conversion
  → Routing rules → VLESS/Hysteria2 outbound → VPS → Headscale/DERP
```

The `auto_route` and `strict_route` options handle system routing table modifications automatically. On Linux, `auto_redirect` (nftables-based) is the recommended mode and avoids conflicts with Docker bridge networks. TLS fragmentation support (since v1.12.0) can fragment ClientHello across multiple TCP segments to defeat SNI-based matching.

**Automatic failover** via `urltest` outbound tests multiple protocols every few minutes and selects the one with lowest latency. When TSPU blocks one protocol, sing-box automatically switches:

```json
{
  "type": "urltest", "tag": "auto-proxy",
  "outbounds": ["vless-reality", "hysteria2", "vmess-ws-cdn"],
  "url": "https://www.gstatic.com/generate_204",
  "interval": "3m", "tolerance": 50,
  "interrupt_exist_connections": true
}
```

**S-UI panel** (v1.3.10, February 2026, **7.6k stars**) provides web-based management for sing-box servers. It supports all sing-box protocols, advanced routing configuration, client subscription links, traffic statistics, and SSL certificate management. The S-UI-PRO variant adds Nginx reverse proxy with 150+ fake website templates for additional camouflage.

---

## Hysteria 2: the high-speed UDP fallback

Hysteria 2 (v2.7.1, February 2026, actively maintained) is built on QUIC and masquerades as HTTP/3 traffic. Its **Brutal congestion control** aggressively fills available bandwidth rather than backing off on packet loss, achieving exceptional throughput on degraded connections — making it ideal as a high-performance secondary protocol.

**DPI resistance**: Appears as standard HTTP/3/QUIC traffic. Without the pre-shared key, the server returns normal web content. **Salamander obfuscation** (optional) wraps QUIC packets in BLAKE2b-256 keyed obfuscation, useful when QUIC itself is blocked but UDP isn't — traffic becomes unrecognizable as any known protocol. Port hopping dynamically changes listening ports to evade port-based blocking.

**Russia-specific**: TSPU's TCP-focused filtering means Hysteria 2 currently passes through significantly better than TCP-based protocols. Many users who lost VLESS access in the November 2025 blocking wave switched to Hysteria 2 successfully. The risk is that Russia could block international QUIC/UDP 443 entirely (already partially done on some ISPs), but this causes massive collateral damage to legitimate HTTP/3 traffic.

**Platform support**: Cross-platform builds for Windows, macOS, Linux, Android, iOS. Integrated into sing-box, v2rayN, v2rayNG, Hiddify, NekoBox. Docker deployment available.

**Performance**: The fastest proxy protocol available. QUIC's built-in multiplexing eliminates head-of-line blocking. Best suited for TCP-over-QUIC proxying where the Brutal congestion control can maximize throughput.

---

## Other solutions ranked by relevance to your requirements

### Amnezia VPN — purpose-built for Russia

Created during a 2020 Russian hackathon by Roskomsvoboda activists, Amnezia is specifically designed for Russian censorship circumvention. It supports **AmneziaWG** (modified WireGuard with junk packets, header randomization, and protocol mimicry), **VLESS+Reality** (via Xray integration), **OpenVPN over Cloak**, and standard protocols. Full cross-platform support (Windows, macOS, Linux, Android, iOS) with GUI-based one-click server deployment to any VPS via SSH.

**AmneziaWG 2.0** introduces full protocol mimicry — traffic can be disguised as QUIC, DNS, SIP, or other UDP protocols, with per-user unique signatures making universal DPI rules impossible. However, HRW's July 2025 report lists AmneziaWG among protocols now being targeted by TSPU, and user reports from June 2025 show it stopped working on MTS and Megafon. When all unknown UDP is dropped (which some Russian ISPs do), AmneziaWG fails entirely — use VLESS+Reality instead.

**Best for**: Users who want a simple GUI-based deployment without deep protocol knowledge. The setup wizard auto-configures appropriate protocols based on censorship severity.

### NaïveProxy — Chrome-perfect TLS fingerprint

NaïveProxy uses Chromium's actual network stack to proxy traffic through HTTP/2 CONNECT tunnels, making it **indistinguishable from genuine Chrome browser traffic** at the TLS level. The sing-box documentation explicitly recommends NaïveProxy over uTLS for TLS fingerprint resistance, noting that uTLS has "fundamental architectural limitations." Application fronting (hiding behind Caddy web server) defeats active probing. Reportedly working in Russia but not tested at scale against the latest TSPU updates. Limited client ecosystem compared to VLESS+Reality.

### Mihomo (Clash Meta) — the rule-based routing layer

Mihomo is primarily a **client**, not a server. It's a rule-based proxy tool that connects to servers running Xray, sing-box, or Hysteria. Its strength is sophisticated traffic routing: rules by domain, IP, process name, and geo-databases, with proxy groups supporting url-test (automatic fastest selection), fallback, and load balancing. TUN mode captures all system traffic. Supported on all platforms via GUI clients including Mihomo Party, FlClash, and Clash Verge Rev.

**For your use case**: Mihomo could replace sing-box as the client-side routing layer if you prefer Clash-format YAML configuration over sing-box's JSON. However, sing-box has broader server-side protocol support and tighter integration with the latest transport innovations (XHTTP, AnyTLS).

### Outline VPN — too limited for Russia

Outline (by Jigsaw/Alphabet) is Shadowsocks-only with recent WebSocket support. Extremely easy to deploy (5-minute GUI setup) and well-maintained (30M+ users/month), but **Shadowsocks is ~95% detected by TSPU**. The WebSocket transport adds resilience but doesn't match VLESS+Reality's stealth. Not recommended as a primary solution for Russia.

### Trojan-GFW/Trojan-Go — declining effectiveness

Trojan disguises traffic as legitimate HTTPS with real TLS certificates and web server fallback for probers. However, both Trojan-GFW and Trojan-Go are **effectively unmaintained** (Trojan-Go's last update: July 2024). Active probing by TSPU defeats it with **~90% detection** since August 2025. The Trojan protocol is still supported within Xray-core and sing-box for legacy compatibility.

### ShadowTLS v3 — promising but vulnerable

ShadowTLS performs a real TLS handshake with a trusted third-party server, then carries Shadowsocks data inside TLS Application Data records. Strong concept, but the **Aparecium vulnerability** demonstrated that ShadowTLS v3 fails to relay NewSessionTicket post-handshake messages and adds detectable 4-byte HMAC overhead to handshake messages. Whether TSPU has deployed this detection is unknown. Best used as a wrapper for Shadowsocks when VLESS+Reality is unavailable.

### V2Ray-core — superseded by Xray-core

V2Ray-core (v2fly, 33k stars) is still maintained but **lacks XTLS-Reality** — the single most important DPI resistance feature. VMess is 80% detected. All clients have migrated to Xray-core as default. Not recommended for new deployments.

### DNSTT — emergency-only last resort

DNS tunneling through DoH/DoT resolvers is extremely difficult to block without breaking DNS itself. Maximum throughput is **~130 KB/s** — suitable only for text-based communication. Useful when every other protocol is blocked, but impractical for daily use or any bandwidth-intensive activity.

---

## Integrating with Headscale and Tailscale

Tailscale relies on WireGuard, which is **100% blocked** in Russia. Tailscale has been observed returning HTTP 451 errors from Russian IPs. There are open feature requests for native proxy support but none implemented. Your mesh **must** be wrapped in a DPI-resistant tunnel.

### Architecture: sing-box TUN as the integration layer

The cleanest approach uses sing-box with TUN mode on client devices inside Russia. sing-box captures all system traffic — including Tailscale's WireGuard packets — at Layer 3 and routes them through VLESS+Reality or Hysteria 2 to your VPS:

```
┌─────────────────────────────────────────────────────┐
│ Client device in Russia                              │
│  Tailscale → WireGuard packets → sing-box TUN       │
│  sing-box routes via VLESS+Reality / Hysteria2       │
└──────────────────────┬──────────────────────────────┘
                       │ Looks like HTTPS to DPI
                       ▼
┌─────────────────────────────────────────────────────┐
│ VPS (Hetzner DE/FI, OVH, BuyVM)                    │
│  sing-box/Xray server (VLESS+Reality :443)          │
│  Headscale coordination server                       │
│  Custom DERP relay (shares :443 with proxy)          │
│  Tailscale node (exit node)                          │
└──────────────────────┬──────────────────────────────┘
                       │ Direct WireGuard
                       ▼
              Other mesh nodes
```

**Critical details**: Set WireGuard MTU to **1300** (accounting for ~120 bytes encapsulation overhead). Exclude the VPS IP from TUN routing to prevent loops (`auto_detect_interface: true` handles this). On Linux, use `auto_redirect` mode to avoid Docker conflicts if you're running containers.

### Alternative: Xray dokodemo-door approach (desktop only)

On desktop Linux/macOS/Windows, you can use Xray's `dokodemo-door` inbound to capture WireGuard UDP on a local port and forward it through VLESS. Point your WireGuard client's endpoint to `127.0.0.1:51820`:

```json
{
  "inbounds": [{"port": 51820, "protocol": "dokodemo-door",
    "settings": {"address": "127.0.0.1", "port": 51820, "network": "udp"}}],
  "outbounds": [{"protocol": "vless", "settings": {"vnext": [{"address": "<VPS>", "port": 443,
    "users": [{"id": "<UUID>", "encryption": "none"}]}]},
    "streamSettings": {"network": "h2", "security": "reality",
      "realitySettings": {"fingerprint": "chrome", "serverName": "www.cloudflare.com",
        "publicKey": "<KEY>", "shortId": "<ID>"}}}]
}
```

**Performance penalty**: WireGuard over VLESS via dokodemo-door shows **~30 Mbps** vs **~150 Mbps** for direct WireGuard — a 5x slowdown in some tests. Using VLESS with UoT (UDP-over-TCP) reportedly achieves near-1Gbps, far better than the dokodemo-door approach. **This method does not work on mobile** — use sing-box TUN mode instead.

### Custom DERP server on the proxy VPS

Run your Headscale DERP relay on the same VPS and domain as your VLESS proxy. DERP uses HTTPS on port 443, so from DPI's perspective, all traffic (proxy + DERP + coordination) appears as ordinary HTTPS to a single domain. Configure Headscale to remove default Tailscale DERP servers and use only your custom one:

```yaml
derp:
  server:
    enabled: true
  urls: []
  paths:
    - /etc/headscale/derp.yaml
```

### Split tunneling for performance

If you want non-mesh traffic to bypass the proxy (for accessing Russian services directly), use sing-box routing rules targeting only Tailscale's CGNAT range and your DERP server:

```json
{"route": {"rules": [
  {"ip_cidr": ["100.64.0.0/10"], "outbound": "vless-proxy"},
  {"domain_suffix": [".ts.net"], "outbound": "vless-proxy"},
  {"ip_cidr": ["<DERP_IP>/32"], "outbound": "vless-proxy"},
  {"outbound": "direct"}
]}}
```

---

## Recommended deployment stack and protocol fallback chain

For a DevOps-oriented deployment maximizing resilience against TSPU:

**Server-side**: Deploy sing-box (or Xray-core with 3x-ui panel) on **2-3 VPS instances** across different providers (Hetzner Finland, OVH France, BuyVM Luxembourg). Each VPS serves multiple protocols simultaneously:

| Protocol | Transport | Port | Purpose |
|---|---|---|---|
| VLESS+Reality | XHTTP | 443 | Primary — highest stealth |
| VLESS+Reality | gRPC | 443 | Secondary TCP option |
| Hysteria 2 | QUIC+Salamander | 8443/UDP | High-speed UDP fallback |
| VLESS+WS | WebSocket+TLS | 443 (via CDN) | CDN-fronted last resort |

**Client-side**: sing-box with TUN mode and `urltest` outbound cycling through all four protocol configurations. Automatic failover when TSPU blocks one variant. Manual `selector` outbound via Clash API dashboard for override.

**Infrastructure as code**: Multiple Ansible roles exist for automated Xray deployment (pilosus/Xray-ansible, Akiyamov/xray-vps-setup). 3x-ui has a ready Docker Compose setup. For sing-box, the sing-box-vps project provides one-click multi-protocol deployment scripts.

**Monitoring**: 3x-ui panel provides traffic monitoring, user management, and Telegram bot integration for alerts. sing-box exposes Clash API endpoints (`/proxies`, `/connections`) for custom monitoring. Use `urltest` interval checks as a built-in health-check mechanism.

**Subscription distribution**: Both 3x-ui and S-UI generate subscription URLs that clients can import. When you rotate VPS IPs or change configurations, update the subscription and clients auto-update within minutes.

---

## Comprehensive comparison of all solutions

| Solution | Type | All 5 platforms | DPI resistance | Russia TSPU (Feb 2026) | Speed | Multi-protocol | Web panel | Maintained |
|---|---|---|---|---|---|---|---|---|
| **Xray-core (VLESS+Reality)** | Client+Server | ✅ (via clients) | ★★★★★ | Best with XHTTP/gRPC | Excellent | 10+ protocols | 3x-ui, Remnawave | Very active |
| **sing-box** | Client+Server | ✅ (native) | ★★★★★ | Excellent | Excellent | 20+ protocols | S-UI | Very active |
| **Hysteria 2** | Client+Server | ✅ | ★★★★☆ | Works (UDP) | Best in class | Single protocol | CLI only | Active |
| **Amnezia VPN** | Client+Server | ✅ | ★★★★☆ | Good (multi-proto) | Good-Excellent | 8 protocols | GUI client | Active |
| **Mihomo (Clash Meta)** | Client only | ✅ | Depends on server | N/A (client) | Good | 10+ protocols | External UI | Active |
| **NaïveProxy** | Client+Server | ⚠️ (limited iOS) | ★★★★★ | Good (untested at scale) | Good | Single protocol | CLI only | Moderate |
| **3x-ui** | Server panel | Linux server | Via Xray | Via Xray | Via Xray | Via Xray | ✅ Web panel | Very active |
| **S-UI** | Server panel | Linux server | Via sing-box | Via sing-box | Via sing-box | Via sing-box | ✅ Web panel | Active |
| **Shadowsocks 2022** | Protocol | ✅ (via clients) | ★★★☆☆ | Blocked standalone | Excellent | Single protocol | Via panels | Active |
| **ShadowTLS v3** | Wrapper | Via sing-box | ★★★★☆ | Uncertain (Aparecium) | Good | Wrapper only | None | Moderate |
| **Outline VPN** | Client+Server | ✅ | ★★★☆☆ | Partially blocked | Good | SS only | ✅ Manager app | Active |
| **Trojan-GFW/Go** | Protocol | ✅ (via clients) | ★★★☆☆ | ~90% detected | Good | Single protocol | Via panels | Abandoned |
| **Cloak** | Wrapper | ✅ (inc. Android) | ★★★★☆ | Good with SS/OpenVPN | Moderate | Wrapper only | CLI | Active |
| **V2Ray-core** | Client+Server | ✅ (via clients) | ★★★☆☆ | Not recommended | Good | 8+ protocols | Via panels | Low activity |
| **AmneziaWG 2.0** | Protocol | ✅ + routers | ★★★★☆ | Periodically blocked | Excellent | WG variant only | Via Amnezia | Active |
| **DNSTT** | Tunnel | ⚠️ (no iOS) | ★★★★☆ | Last resort | ~130 KB/s | Single method | CLI | Maintained |
| **WebTunnel (Tor)** | Transport | Tor ecosystem | ★★★★★ | High (fresh bridges) | Moderate | Tor only | None | Active |
| **Snowflake (Tor)** | Transport | Tor ecosystem | ★★★★☆ | Moderate-High | Low | Tor only | None | Active |

---

## What the Russian user community actually reports working

Community consensus from ntc.party, Habr, GitHub issues, and user reports as of February 2026 converges on these practical findings:

**Working reliably**: VLESS+Reality with XHTTP or gRPC transport, Hysteria 2 (especially on ISPs that don't block unknown UDP), VLESS+WebSocket through CDN (with Cloudflare throttling caveats), and carefully configured AmneziaWG 2.0. Self-hosted solutions on non-obvious IP ranges significantly outperform commercial VPNs.

**Stopped working**: Standard VLESS+Reality+Vision over TCP+TLS (as of February 17, 2026 across many regions), all commercial VPNs using standard protocols, bare Shadowsocks, Trojan (active probing defeats it), standard WireGuard and OpenVPN.

**Regional variance is enormous**: what works in Moscow may fail in Novosibirsk. Different ISPs (Rostelecom, MTS, Megafon, Beeline) run different TSPU configurations. Switching between WiFi and mobile data can bypass blocks because home and mobile TSPU instances are configured differently. Recommended apps from user communities: **Hiddify** (all platforms), **NekoBox** (Android/Windows), **v2rayN/v2rayNG** (desktop/Android), **Streisand** (iOS).

**Critical user advice**: Download and configure VPN tools **before** entering Russia. Maintain at least 3-4 protocol configurations across 2+ VPS providers. Enable automatic failover. Keep all proxy software updated — the TSPU team actively fingerprints older versions (e.g., via Aparecium's NewSessionTicket analysis targeting outdated Xray builds).

## Conclusion

The optimal architecture for your requirements is a **sing-box TUN client** on every device → **multi-protocol sing-box or Xray servers** on 2-3 geographically distributed VPS instances → **Headscale coordination + custom DERP** colocated on one of those VPS nodes. VLESS+Reality with XHTTP transport is your primary protocol; Hysteria 2 with Salamander obfuscation is your high-speed UDP fallback; VLESS+WebSocket through Cloudflare is your CDN-fronted emergency option. The `urltest` outbound in sing-box provides automatic failover between all three.

The key architectural insight is that **no single protocol will remain unblocked indefinitely**. Russia's TSPU team updates detection signatures weekly. The winning strategy is protocol agility — the ability to switch between fundamentally different traffic profiles (TLS-mimicking TCP, QUIC-masquerading UDP, CDN-fronted WebSocket) faster than TSPU can adapt. sing-box's 20+ protocol support and automatic failover mechanism make it the strongest platform for this arms race. Pair it with Ansible-automated VPS provisioning and subscription-based client configuration distribution, and you have an infrastructure that can rotate protocols and endpoints within minutes of a new blocking event.
