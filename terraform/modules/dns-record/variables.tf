variable "zone_id" {
  type        = string
  description = "Cloudflare zone."
}

variable "name" {
  type        = string
  description = "Имя записи внутри зоны, без домена."
}

variable "ipv4_address" {
  type        = string
  default     = null
  description = "Адрес для A-записи."
}

variable "ipv6_address" {
  type        = string
  default     = null
  description = "Адрес для AAAA-записи."
}

# Флаги, а не проверка адреса на null: адрес сервера, который terraform
# только собирается создать, на этапе плана неизвестен, и count по нему
# падает с «Invalid count argument».
variable "enable_ipv4" {
  type        = bool
  default     = true
  description = "Создавать ли A-запись."
}

variable "enable_ipv6" {
  type        = bool
  default     = true
  description = "Создавать ли AAAA-запись."
}

variable "aliases" {
  type = map(object({
    target  = string
    proxied = bool
  }))
  default     = {}
  description = <<-EOT
    CNAME-записи, указывающие на эту машину: ключ — имя записи,
    target — куда указывает. Проксируемые записи прячут адрес сервера
    за Cloudflare, непроксируемые оставляют его видимым.
  EOT
}

variable "ttl" {
  type        = number
  default     = 300
  description = "TTL непроксируемых записей. У проксируемых он всегда automatic."
}

variable "proxied" {
  type        = bool
  default     = false
  description = <<-EOT
    Проксировать ли A/AAAA. Для машин, до которых ходят не только
    браузером (ssh, DERP, tailnet), должно оставаться false — иначе
    наружу видно только адреса Cloudflare.
  EOT
}
