# ──────────────────────────────────────────────
# DNS
#
# Записи вынесены из модуля машины: имя нужно и серверам, созданным не
# терраформом (HostHatch, Mivocloud, домашний Proxmox). Такой машине
# достаточно вызвать этот модуль с её адресами — без hcloud вообще.
# ──────────────────────────────────────────────

module "vpn_dns" {
  source   = "./modules/dns-record"
  for_each = var.vpn_servers

  zone_id      = var.cloudflare_zone_id
  name         = "${each.key}.vpn"
  ipv4_address = module.vpn_server[each.key].ipv4_address
  ipv6_address = module.vpn_server[each.key].ipv6_address
}

module "server_dns" {
  source   = "./modules/dns-record"
  for_each = var.servers

  zone_id      = var.cloudflare_zone_id
  name         = each.key
  ipv4_address = module.server[each.key].ipv4_address
  ipv6_address = module.server[each.key].ipv6_address

  # Сервисные имена висят алиасами на записи control-плоскости и
  # проксируются Cloudflare — адрес сервера наружу не виден.
  aliases = each.value.role == "control" ? {
    vpn     = { target = "${each.key}.${var.domain}", proxied = true }
    sub     = { target = "${each.key}.${var.domain}", proxied = true }
    traefik = { target = "${each.key}.${var.domain}", proxied = true }
  } : {}
}

# mesh остаётся отдельной A-записью, а не алиасом: headscale раздаёт
# клиентам адрес узла для DERP, и проксировать его нельзя.
module "mesh_dns" {
  source = "./modules/dns-record"
  count  = local.control_server != null ? 1 : 0

  zone_id      = var.cloudflare_zone_id
  name         = "mesh"
  ipv4_address = module.server[local.control_server].ipv4_address
  enable_ipv6  = false
}

# ──────────────────────────────────────────────
# Переезд адресов после выделения модуля dns-record.
#
# Без этих блоков terraform считает прежние записи удалёнными, а новые —
# создаваемыми, то есть на несколько минут снимает DNS у живых сервисов.
# План после рефакторинга обязан показать 0 to add, 0 to destroy.
# ──────────────────────────────────────────────

moved {
  from = module.vpn_server["hel-01"].cloudflare_dns_record.ipv4
  to   = module.vpn_dns["hel-01"].cloudflare_dns_record.ipv4[0]
}

moved {
  from = module.vpn_server["hel-01"].cloudflare_dns_record.ipv6
  to   = module.vpn_dns["hel-01"].cloudflare_dns_record.ipv6[0]
}

moved {
  from = module.server["htz-hel-01"].cloudflare_dns_record.ipv4
  to   = module.server_dns["htz-hel-01"].cloudflare_dns_record.ipv4[0]
}

moved {
  from = module.server["htz-hel-01"].cloudflare_dns_record.ipv6
  to   = module.server_dns["htz-hel-01"].cloudflare_dns_record.ipv6[0]
}

moved {
  from = module.server["htz-hel-02"].cloudflare_dns_record.ipv4
  to   = module.server_dns["htz-hel-02"].cloudflare_dns_record.ipv4[0]
}

moved {
  from = module.server["htz-hel-02"].cloudflare_dns_record.ipv6
  to   = module.server_dns["htz-hel-02"].cloudflare_dns_record.ipv6[0]
}

# Прежние CNAME лежали плоскими ресурсами с count; теперь это for_each
# внутри модуля, поэтому индекс меняется на имя записи.
moved {
  from = cloudflare_dns_record.panel[0]
  to   = module.server_dns["htz-hel-01"].cloudflare_dns_record.cname["vpn"]
}

moved {
  from = cloudflare_dns_record.subscription[0]
  to   = module.server_dns["htz-hel-01"].cloudflare_dns_record.cname["sub"]
}

moved {
  from = cloudflare_dns_record.traefik[0]
  to   = module.server_dns["htz-hel-01"].cloudflare_dns_record.cname["traefik"]
}

moved {
  from = cloudflare_dns_record.mesh[0]
  to   = module.mesh_dns[0].cloudflare_dns_record.ipv4[0]
}
