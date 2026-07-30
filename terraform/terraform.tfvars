# DEPRECATED FREEZE (2026-06-22): VPN-ноды теперь управляются
# вручную через Mivocloud + Ansible (см. ansible/playbooks/vpn-node-deploy.yml).
# Terraform отвечает только за control-plane (htz-hel-01 с RemnaWave).
# Автотриггеры workflow убраны (см. .github/workflows/terraform.yml).
# Перед `terraform apply` ВСЕГДА смотреть `terraform plan` глазами —
# случайные изменения tfvars могут пересоздать или удалить prod-серверы.

domain             = "cosmdandy.dev"
cloudflare_zone_id = "1c6c22b9c953bcffffa5aec356eb547e"

ssh_public_keys = ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDsx73RvU7CaBdKkAcRXcLdIG/APXzi5l4sxY+5J57EV cosmdandy@macbook-cosmdandy"]

acme_email = "tkondrashin@icloud.com"

servers = {
  htz-hel-01 = {
    location = "hel1"
    type     = "cax11"
    role     = "control"
    # Снято 30.07.2026: панель переехала на hhh-sto-02, машина выводится
    # из эксплуатации. Пока стоит true, apply на удаление падает — это и
    # есть смысл флага. Вернуть true, если машина внезапно останется.
    protected = false
    tcp_ports = [80, 443, 3478]
    # 41641 — прямые соединения tailscale. Был открыт руками в панели
    # Hetzner и отсутствовал здесь, поэтому apply закрыл бы его и увёл
    # весь трафик tailnet на DERP.
    udp_ports = [3478, 41641]
  }
  # htz-hel-02 удалён в Hetzner; описание убрано, чтобы apply не поднял
  # его заново. Ноды Remnawave разворачиваются на машинах провайдеров,
  # до которых дотягивается DPI — см. docs/dpi-report-22-06-26.md.
}
