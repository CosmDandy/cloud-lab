variable "hcloud_token" {
  type      = string
  sensitive = true
}

variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}

variable "cloudflare_zone_id" {
  type = string
}

variable "domain" {
  type    = string
  default = "cosmdandy.dev"
}

variable "ssh_public_keys" {
  type = list(string)
}

variable "acme_email" {
  type = string
}

variable "servers" {
  type = map(object({
    location  = string
    type      = string
    role      = string
    tcp_ports = list(number)
    udp_ports = list(number)
    image     = optional(string, "ubuntu-24.04")
    labels    = optional(map(string), {})
    # Защита от удаления. По умолчанию включена: машины в этом модуле
    # держат состояние, которое плейбуком не пересоздать. Снимается
    # отдельным apply перед выводом машины из эксплуатации — так удаление
    # требует двух осознанных шагов, а не одного.
    protected = optional(bool, true)
  }))
  default = {}
}
