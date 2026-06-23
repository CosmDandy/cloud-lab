# DEPRECATED FREEZE (2026-06-22): VPN-ноды теперь управляются
# вручную через Mivocloud + Ansible (см. ansible/playbooks/vpn-node-deploy.yml).
# Terraform отвечает только за control-plane (htz-hel-01 с RemnaWave).
# Автотриггеры workflow убраны (см. .github/workflows/terraform.yml).
# Перед `terraform apply` ВСЕГДА смотреть `terraform plan` глазами —
# случайные изменения tfvars могут пересоздать или удалить prod-серверы.

domain             = "cosmdandy.dev"
cloudflare_zone_id = "1c6c22b9c953bcffffa5aec356eb547e"
github_owner       = "cosmdandy"
github_repository  = "vpn-infra"

ssh_public_keys = ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDsx73RvU7CaBdKkAcRXcLdIG/APXzi5l4sxY+5J57EV cosmdandy@macbook-cosmdandy"]

acme_email = "tkondrashin@icloud.com"

vpn_servers = {
  hel-01 = {
    location  = "hel1"
    type      = "cax11"
    tcp_ports = [80, 443, 8443, 8446, 5201]
    udp_ports = [443, 5201]
  }
}

servers = {
  htz-hel-01 = {
    location  = "hel1"
    type      = "cax11"
    role      = "control"
    tcp_ports = [80, 443, 3478]
    udp_ports = [3478]
  }
  htz-hel-02 = {
    location  = "hel1"
    type      = "cax11"
    role      = "node"
    tcp_ports = [443, 2222]
    udp_ports = [443]
  }
}
