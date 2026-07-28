terraform {
  required_providers {
    hcloud = {
      source = "hetznercloud/hcloud"
    }
  }
}

# ──────────────────────────────────────────────
# Hetzner Cloud Server
# ──────────────────────────────────────────────

resource "hcloud_server" "this" {
  name        = var.name
  server_type = var.server_type
  image       = var.image
  location    = var.location
  ssh_keys    = var.ssh_key_ids
  user_data   = var.cloud_init

  labels = merge(var.labels, {
    managed-by = "terraform"
  })

  lifecycle {
    ignore_changes = [user_data]
  }

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }
}

# ──────────────────────────────────────────────
# Hetzner Firewall
# ──────────────────────────────────────────────

resource "hcloud_firewall" "this" {
  name = "fw-${var.name}"

  # SSH — always open
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # ICMP — always open
  rule {
    direction  = "in"
    protocol   = "icmp"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # Dynamic TCP ports
  dynamic "rule" {
    for_each = var.tcp_ports
    content {
      direction  = "in"
      protocol   = "tcp"
      port       = tostring(rule.value)
      source_ips = ["0.0.0.0/0", "::/0"]
    }
  }

  # Dynamic UDP ports
  dynamic "rule" {
    for_each = var.udp_ports
    content {
      direction  = "in"
      protocol   = "udp"
      port       = tostring(rule.value)
      source_ips = ["0.0.0.0/0", "::/0"]
    }
  }
}

resource "hcloud_firewall_attachment" "this" {
  firewall_id = hcloud_firewall.this.id
  server_ids  = [hcloud_server.this.id]
}
