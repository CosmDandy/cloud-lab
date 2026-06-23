## VPN Infrastructure Platform

Self-hosted multi-protocol VPN platform on Hetzner Cloud with full IaC, automated deployments, and observability. Built as a personal project to gain hands-on experience with production-grade DevOps practices.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  htz-hel-01 (Control Plane)                             │
│                                                         │
│  Caddy ─► Remnawave Panel    ─► PostgreSQL, Redis  [WIP]│
│        ─► Subscription Page                        [WIP]│
│        ─► Headscale (mesh VPN control)                  │
│        ─► Headplane (admin UI)                          │
│        ─► Grafana                                  [WIP]│
│                                                         │
│  VictoriaMetrics ◄─ node-exporter, cAdvisor,       [WIP]│
│  VMAlert (alerting) │ Loki + Promtail (logs)       [WIP]│
└────────────┬────────────────────────────────────────────┘
             │ metrics scrape
┌────────────▼────────────────────────────────────────────┐
│  htz-hel-02 (VPN Node)                                  │
│                                                         │
│  Remnawave Node (VLESS Reality + XHTTP + gRPC)          │
│  node-exporter                                     [WIP]│
└─────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Tools | Status |
|-------|-------|--------|
| **Infrastructure** | Terraform (HCP Terraform backend), Hetzner Cloud (ARM instances), Cloudflare DNS | Deployed |
| **Configuration** | Ansible (server bootstrap, Docker, sysctl tuning, SSH hardening, GitHub runner provisioning) | **[WIP]** — skeleton created, roles not implemented; currently handled by cloud-init |
| **Reverse Proxy** | Caddy 2.9 (automatic TLS, HTTP→HTTPS, reverse proxy for 5 services) | **[WIP]** — config ready, migration from Traefik not deployed yet |
| **VPN** | Remnawave (VLESS + Reality + Vision/gRPC/XHTTP), legacy sing-box (Hysteria2 + Salamander) | Deployed |
| **Mesh VPN** | Headscale 0.28 (self-hosted Tailscale control), Headplane (web UI), DERP relay | Deployed |
| **Monitoring** | VictoriaMetrics, Grafana 11.6, VMAlert, Loki + Promtail, node-exporter, cAdvisor | **[WIP]** — configs ready, Terraform changes (DNS, secrets, firewall) pending |
| **CI/CD** | GitHub Actions — 6 workflows, self-hosted runners on Hetzner, matrix deployments | Deployed (monitoring workflow pending first deploy) |
| **Databases** | PostgreSQL 17, Redis 7 | Deployed |

### Key Implementation Details

- **3 Hetzner Cloud ARM servers** (cax11) provisioned via Terraform with cloud-init bootstrap
- **17 Docker containers** across 4 composable stacks (`control`, `monitoring`, `node`, `vpn-legacy`) — **[WIP]** monitoring stack (7 containers) not deployed yet; currently 10 running
- **GitOps deployment model**: push to `master` triggers `envsubst` template rendering → `rsync` → `docker compose up` on self-hosted runners — no SSH keys in CI/CD
- **Secrets management**: Terraform generates random credentials, stores them in GitHub Actions environment secrets; no plaintext secrets in the repo
- **Monitoring**: pull-based metrics collection (VictoriaMetrics scrapes node-exporters across servers), centralized logging via Loki, alerting rules for CPU/memory/disk/container health — **[WIP]**
- **Multi-protocol VPN**: VLESS + Reality (anti-DPI) with Vision, gRPC, and XHTTP transports; geo-based routing (direct for RU, WARP for streaming services)
- **Mesh networking**: Headscale with MagicDNS, custom DERP server, Taildrop file sharing
- **Network hardening**: BBR congestion control, TCP Fast Open, SSH key-only auth, Hetzner Cloud firewalls per server role

### Repository Structure

```
terraform/         — Infrastructure as Code (servers, DNS, firewalls, secrets)
ansible/           — Server configuration (base OS, Docker, GitHub runners) [WIP]
stacks/            — Docker Compose stacks (control, monitoring, node, vpn-legacy)
scripts/           — CI utilities (API sync scripts)
.github/workflows/ — 6 deployment pipelines
```
