output "fqdn" {
  value       = try(cloudflare_dns_record.ipv4[0].name, cloudflare_dns_record.ipv6[0].name, null)
  description = "Полное имя записи, как его вернул Cloudflare."
}

output "alias_fqdns" {
  value       = { for k, r in cloudflare_dns_record.cname : k => r.name }
  description = "Полные имена созданных CNAME."
}
