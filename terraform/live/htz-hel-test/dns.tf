module "dns" {
  source = "../../modules/dns-record"

  zone_id      = var.cloudflare_zone_id
  name         = var.server_name
  ipv4_address = module.server.ipv4_address
  ipv6_address = module.server.ipv6_address

  # Имена боевые, а не -test: redirect URI OIDC-клиентов прописываются с
  # реальными URL, и на временных именах их пришлось бы заводить дважды.
  # mesh и traefik освободил корневой модуль — там они указывали на мёртвую
  # установку headscale и на дашборд, который наружу не нужен.
  #
  # Не проксируются: headscale раздаёт клиентам адрес узла для DERP, и за
  # Cloudflare виден был бы только он.
  aliases = {
    for name in ["mesh", "oidc", "grafana", "status", "traefik"] :
    name => {
      target  = "${var.server_name}.${var.domain}"
      proxied = false
    }
  }

  comment = "стенд control-plane"
}
