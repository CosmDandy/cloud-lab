resource "hcloud_ssh_key" "default" {
  count      = length(var.ssh_public_keys)
  name       = "terraform-${count.index}"
  public_key = var.ssh_public_keys[count.index]
}

data "github_actions_registration_token" "this" {
  repository = var.github_repository
}

locals {
  all_runners = merge(
    { for k, _ in var.vpn_servers : "vpn-${k}" => "vpn-${k}" },
    { for k, _ in var.servers : k => k },
  )
  control_server  = one([for k, v in var.servers : k if v.role == "control"])
  control_servers = { for k, v in var.servers : k => v if v.role == "control" }
  node_servers    = { for k, v in var.servers : k => v if v.role == "node" }
}

resource "null_resource" "runner_cleanup" {
  for_each = local.all_runners

  triggers = {
    runner_name = each.value
    repo        = "${var.github_owner}/${var.github_repository}"
    token       = var.github_token
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      RUNNER_ID=$(curl -sf \
        -H "Authorization: token ${self.triggers.token}" \
        "https://api.github.com/repos/${self.triggers.repo}/actions/runners" \
        | jq -r '.runners[] | select(.name == "${self.triggers.runner_name}") | .id')
      if [ -n "$RUNNER_ID" ] && [ "$RUNNER_ID" != "null" ]; then
        curl -sf -X DELETE \
          -H "Authorization: token ${self.triggers.token}" \
          "https://api.github.com/repos/${self.triggers.repo}/actions/runners/$RUNNER_ID"
        echo "Removed runner ${self.triggers.runner_name} (ID: $RUNNER_ID)"
      fi
    EOT
  }
}

# ──────────────────────────────────────────────
# VPN servers (LEGACY, DEPRECATED 2026-06-22)
#
# VPN-ноды теперь управляются вручную через Mivocloud + Ansible
# (см. ansible/playbooks/vpn-node-deploy.yml). Этот модуль
# остаётся ради backward compatibility tfstate. НЕ применять
# `terraform apply` без явного решения — это может пересоздать
# legacy hcloud VPN-серверы.
# ──────────────────────────────────────────────

module "vpn_server" {
  source   = "./modules/hcloud-server"
  for_each = var.vpn_servers

  name        = "vpn-${each.key}"
  dns_name    = "${each.key}.vpn"
  location    = each.value.location
  server_type = each.value.type
  image       = each.value.image
  ssh_key_ids = hcloud_ssh_key.default[*].id
  tcp_ports   = each.value.tcp_ports
  udp_ports   = each.value.udp_ports

  labels = merge(each.value.labels, {
    role = "vpn"
  })

  cloud_init = templatefile("${path.module}/cloud-init/vpn.yaml.tftpl", {
    ssh_public_keys   = var.ssh_public_keys
    runner_token      = data.github_actions_registration_token.this.token
    runner_name       = "vpn-${each.key}"
    runner_labels     = "hcloud-vpn-${each.key}"
    github_repository = "${var.github_owner}/${var.github_repository}"
  })

  cloudflare_zone_id = var.cloudflare_zone_id
  domain             = var.domain
}

# ──────────────────────────────────────────────
# Unified servers (Remnawave architecture)
# ──────────────────────────────────────────────

module "server" {
  source   = "./modules/hcloud-server"
  for_each = var.servers

  name        = each.key
  dns_name    = each.key
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

  cloud_init = templatefile("${path.module}/cloud-init/server.yaml.tftpl", {
    ssh_public_keys   = var.ssh_public_keys
    runner_token      = data.github_actions_registration_token.this.token
    runner_name       = each.key
    runner_labels     = "hcloud-${each.key}"
    github_repository = "${var.github_owner}/${var.github_repository}"
  })

  cloudflare_zone_id = var.cloudflare_zone_id
  domain             = var.domain
}
