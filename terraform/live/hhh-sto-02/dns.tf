# ──────────────────────────────────────────────
# Боевой control-plane: hhh-sto-02, HostHatch Стокгольм
#
# Сюда переезжает то, что репетировалось на htz-hel-test. Причина переезда
# не в самой машине, а в доступности: Hetzner с домашнего канала не берётся
# (0 байт за 11 с), HostHatch берётся (10.7 МБ/с, замер 30.07.2026), а
# mesh/oidc/grafana/status/traefik — непроксируемые записи, то есть ходят
# прямо на адрес сервера.
#
# ВНИМАНИЕ к порядку применения: те же пять CNAME сейчас принадлежат
# воркспейсу htz-hel-test. Cloudflare не даёт двум записям одно имя, поэтому
# сначала применяется удаление алиасов там, потом создание здесь. Разрыв —
# около минуты плюс TTL 300 у резолверов, которые успеют закешировать
# отрицательный ответ. Делать наоборот нельзя: apply здесь упадёт на
# конфликте имён.
# ──────────────────────────────────────────────

module "dns" {
  source = "../../modules/dns-record"

  zone_id      = var.cloudflare_zone_id
  name         = var.server_name
  ipv4_address = var.ipv4_address

  enable_ipv6  = var.enable_ipv6
  ipv6_address = var.ipv6_address

  # Не проксируются, и это не недосмотр: headscale раздаёт клиентам адрес
  # узла под встроенный DERP, а за Cloudflare виден был бы только адрес
  # Cloudflare. Панель и подписки (vpn, sub) — наоборот проксируемые, но
  # они живут в корневом модуле и переезжают отдельно, последними.
  aliases = {
    for name in ["mesh", "oidc", "grafana", "status", "traefik"] :
    name => {
      target  = "${var.server_name}.${var.domain}"
      proxied = false
    }
  }

  comment = "боевой control-plane"
}
