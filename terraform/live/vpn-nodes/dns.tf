# ──────────────────────────────────────────────
# Имена VPN-нод под Hysteria2.
#
# Четвёртый уровень выбран намеренно: `*.vpn.cosmdandy.dev` отделяет
# пользовательские имена от инфраструктурных (mesh, oidc, grafana живут
# третьим уровнем на control-plane).
#
# Ограничение Cloudflare «Universal SSL только на один уровень поддоменов»
# здесь не работает: сертификат выпускает Let's Encrypt через ACME DNS-01
# прямо на ноде, Cloudflare только держит зону и принимает TXT для
# валидации. Вложенность LE не ограничивает.
#
# Записи непроксируемые и не могут быть иными: Cloudflare не проксирует UDP,
# а Hysteria2 — это QUIC.
# ──────────────────────────────────────────────

module "node_dns" {
  source   = "../../modules/dns-record"
  for_each = var.nodes

  zone_id      = var.cloudflare_zone_id
  name         = "${each.key}.vpn"
  ipv4_address = each.value.ipv4_address

  # HostHatch глобальный IPv6 нодам не выдал — проверено на всех трёх
  # 15.08.2026. AAAA заводить нельзя: клиент с рабочим v6 предпочёл бы её
  # и попал в никуда.
  enable_ipv6 = false

  comment = "VPN-нода ${each.value.country_code}, Hysteria2"
}
