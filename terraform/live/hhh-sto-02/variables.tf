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

variable "server_name" {
  type    = string
  default = "hhh-sto-02"
}

# Адрес вводится руками: машина куплена в панели HostHatch, провайдера
# терраформа у них нет. Если сервер будет пересоздан, адрес меняется здесь.
variable "ipv4_address" {
  type = string
}

# IPv6 на машине не выдан: в системе только 167.104.104.209/24, глобального
# v6-адреса и маршрута по умолчанию нет (проверено на хосте 30.07.2026).
# Заводить AAAA нельзя — клиенты с работающим IPv6 предпочли бы её и попали
# в никуда. Включить, когда HostHatch выдаст подсеть.
variable "enable_ipv6" {
  type    = bool
  default = false
}

variable "ipv6_address" {
  type    = string
  default = null
}
