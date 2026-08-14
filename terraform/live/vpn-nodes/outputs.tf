output "node_names" {
  description = "Имена нод под Hysteria2, для конфигов клиента и ACME."
  value       = { for k, v in var.nodes : k => "${k}.vpn.${var.domain}" }
}
