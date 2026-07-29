# ──────────────────────────────────────────────
# DNS
#
# Записи вынесены из модуля машины: имя нужно и серверам, созданным не
# терраформом (HostHatch, Mivocloud, домашний Proxmox). Такой машине
# достаточно вызвать этот модуль с её адресами — без hcloud вообще.
# ──────────────────────────────────────────────

module "server_dns" {
  source   = "./modules/dns-record"
  for_each = var.servers

  zone_id      = var.cloudflare_zone_id
  name         = each.key
  ipv4_address = module.server[each.key].ipv4_address
  ipv6_address = module.server[each.key].ipv6_address

  # Сервисные имена висят алиасами на записи control-плоскости и
  # проксируются Cloudflare — адрес сервера наружу не виден.
  #
  # traefik отсюда убран: дашборд снаружи не нужен никому, а имя понадобилось
  # стенду. Вместе с ним ушла и отдельная A-запись mesh — установка headscale
  # на этой машине нерабочая (узлы offline с мая), боевой tailnet живёт на
  # mesh.cosmdandy.ru. Обе записи удаляются по-настоящему.
  aliases = each.value.role == "control" ? {
    vpn = { target = "${each.key}.${var.domain}", proxied = true }
    sub = { target = "${each.key}.${var.domain}", proxied = true }
  } : {}
}

# Блоки moved, переносившие записи в модуль dns-record, удалены: перенос
# применён (коммит 8d7e880), в состоянии адреса уже новые, и дальше эти
# блоки — мёртвый код. Часть из них вдобавок указывала на ресурсы, которых
# в конфигурации больше нет.
