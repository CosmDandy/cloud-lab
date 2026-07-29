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

variable "github_token" {
  type      = string
  sensitive = true
}

variable "github_owner" {
  type = string
}

variable "github_repository" {
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
  }))
  default = {}
}
