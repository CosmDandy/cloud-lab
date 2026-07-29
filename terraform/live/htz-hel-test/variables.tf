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

# Имя ключа в проекте Hetzner, а не сам ключ: отпечаток в проекте уникален,
# и второе создание того же ключа провайдер отвергает — здесь он только
# ищется data-источником.
#
# В проекте стенда ключ лежит под именем cosmdandy (id 115900757), отпечаток
# MD5:9e:5c:a5:de:b9:c0:8c:d5:e5:41:01:d8:f5:3e:d3:1a — тот же материал, что
# в ssh_public_keys ниже, проверено ssh-keygen -lf. В проекте боевого
# htz-hel-01 тот же ключ называется terraform-0: имена ключей живут внутри
# проекта, а проекты у стенда и прода разные.
variable "ssh_key_name" {
  type    = string
  default = "cosmdandy"
}

variable "server_name" {
  type    = string
  default = "htz-hel-test"
}

variable "location" {
  type    = string
  default = "hel1"
}

# x86, а не ARM боевого cax11: едем на HostHatch, а он x86 — репетировать
# надо ту архитектуру, куда переезжаем, а не ту, откуда.
#
# 4 ГБ — столько же, сколько у прода, и это тот размер, в который стек
# должен влезть. cpx22 даёт те же 4 ГБ за $22.99 против $6.49 у cx23, а
# разница между ними — вдвое больший диск, который стенду не нужен.
# cx23 доступен в hel1 и nbg1, но не в fsn1 (проверено по API 29.07).
variable "server_type" {
  type    = string
  default = "cx23"
}
