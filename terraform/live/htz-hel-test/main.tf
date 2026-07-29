# ──────────────────────────────────────────────
# Стенд control-plane
#
# Репетиция переезда: на чистой машине прогоняются все роли, кроме panel.
# Панель переезжает отдельно и последней — дампом постгреса, чтобы
# пользователи VPN не заметили, — поэтому vpn и sub остаются на htz-hel-01.
# ──────────────────────────────────────────────

data "hcloud_ssh_key" "default" {
  name = var.ssh_key_name
}

module "server" {
  source = "../../modules/hcloud-server"

  name        = var.server_name
  location    = var.location
  server_type = var.server_type
  ssh_key_ids = [data.hcloud_ssh_key.default.id]

  # 80 и 443 — traefik, 3478/udp — STUN встроенного DERP, 41641/udp —
  # прямые соединения tailscale: без него трафик tailnet уходит на релей
  # целиком.
  tcp_ports = [80, 443]
  udp_ports = [3478, 41641]

  labels = {
    role = "control"
    # Стенд, а не прод: машина пересоздаётся свободно, состояния на ней нет.
    stand = "true"
  }

  cloud_init = templatefile("${path.module}/../../cloud-init/server.yaml.tftpl", {
    ssh_public_keys = var.ssh_public_keys
  })
}
