resource "hcloud_ssh_key" "default" {
  count      = length(var.ssh_public_keys)
  name       = "terraform-${count.index}"
  public_key = var.ssh_public_keys[count.index]
}

locals {
  # Имена машин. Раньше их отдавал модуль hcloud-server, но после выноса
  # DNS в отдельный модуль имя перестало быть свойством машины: сервер
  # может быть не hcloud, а запись всё равно нужна.
  server_fqdn     = { for k, _ in var.servers : k => "${k}.${var.domain}" }
  control_servers = { for k, v in var.servers : k => v if v.role == "control" }
}

# ──────────────────────────────────────────────
# Unified servers (Remnawave architecture)
#
# Legacy-модуль vpn_server удалён: var.vpn_servers был пуст, то есть в
# состоянии не было ни одного инстанса и удаление кода ничего не трогает.
# VPN-ноды живут на Mivocloud и управляются ансиблом.
# ──────────────────────────────────────────────

module "server" {
  source   = "./modules/hcloud-server"
  for_each = var.servers

  name        = each.key
  location    = each.value.location
  server_type = each.value.type
  image       = each.value.image
  ssh_key_ids = hcloud_ssh_key.default[*].id
  tcp_ports   = each.value.tcp_ports
  udp_ports   = each.value.udp_ports

  labels = merge(
    each.value.labels,
    { "role" = each.value.role },
  )

  # Control-плоскость держит состояние, которое нельзя пересоздать
  # плейбуком, поэтому удаляется только осознанно — через снятие флага.
  protected = each.value.role == "control"

  cloud_init = templatefile("${path.module}/cloud-init/server.yaml.tftpl", {
    ssh_public_keys = var.ssh_public_keys
  })

}
