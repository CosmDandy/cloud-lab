variable "name" {
  type = string
}

variable "location" {
  type = string
}

variable "server_type" {
  type    = string
  default = "cax11"
}

variable "image" {
  type    = string
  default = "ubuntu-24.04"
}

variable "ssh_key_ids" {
  type = list(number)
}

variable "cloud_init" {
  type = string
}

variable "tcp_ports" {
  type = list(number)
}

variable "udp_ports" {
  type = list(number)
}

variable "labels" {
  type    = map(string)
  default = {}
}

