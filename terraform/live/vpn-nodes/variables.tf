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

# Ноды одной картой, а не по стеку на каждую: содержания у них ровно на одну
# A-запись, и три воркспейса ради этого дали бы три места для рассинхрона.
# Выделять ноду в свой стек имеет смысл, когда у неё появится собственная
# инфраструктура помимо имени.
variable "nodes" {
  type = map(object({
    ipv4_address = string
    country_code = string
  }))
}
