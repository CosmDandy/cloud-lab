output "vpn_servers" {
  value = {
    for name, s in module.vpn_server : name => {
      ipv4 = s.ipv4_address
      ipv6 = s.ipv6_address
      fqdn = local.vpn_fqdn[name]
    }
  }
}

output "servers" {
  value = {
    for name, s in module.server : name => {
      ipv4 = s.ipv4_address
      ipv6 = s.ipv6_address
      fqdn = local.server_fqdn[name]
      role = var.servers[name].role
    }
  }
}
