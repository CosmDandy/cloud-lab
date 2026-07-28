terraform {
  required_providers {
    cloudflare = {
      source = "cloudflare/cloudflare"
    }
  }
}

# Записи заводятся отдельно от машины намеренно: сервер может быть создан
# не терраформом (HostHatch, Mivocloud, домашний Proxmox), а имя ему всё
# равно нужно. Такой машине достаточно передать сюда её адреса.

resource "cloudflare_dns_record" "ipv4" {
  count = var.enable_ipv4 ? 1 : 0

  zone_id = var.zone_id
  name    = var.name
  type    = "A"
  content = var.ipv4_address
  ttl     = var.ttl
  proxied = var.proxied
}

resource "cloudflare_dns_record" "ipv6" {
  count = var.enable_ipv6 ? 1 : 0

  zone_id = var.zone_id
  name    = var.name
  type    = "AAAA"
  content = var.ipv6_address
  ttl     = var.ttl
  proxied = var.proxied
}

# Алиасы на то же имя: панель, подписки, дашборд прокси. Отдельным ресурсом,
# потому что у CNAME своя логика проксирования и ttl.
resource "cloudflare_dns_record" "cname" {
  for_each = var.aliases

  zone_id = var.zone_id
  name    = each.key
  type    = "CNAME"
  content = each.value.target
  # ttl = 1 означает «automatic» и обязателен для проксируемых записей.
  ttl     = each.value.proxied ? 1 : var.ttl
  proxied = each.value.proxied
}
