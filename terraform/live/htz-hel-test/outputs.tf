output "server_ipv4" {
  value       = module.server.ipv4_address
  description = "Вписать в ansible/inventory/cloud.yml после apply."
}

output "server_ipv6" {
  value = module.server.ipv6_address
}
