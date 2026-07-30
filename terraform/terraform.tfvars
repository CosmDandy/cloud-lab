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
  # Пусто, и это конечное состояние, а не временное.
  #
  # htz-hel-01 удалён 31.07.2026: панель переехала на hhh-sto-02 в
  # HostHatch, а Hetzner с домашнего канала не открывается. Перед
  # удалением проверено — ноль запросов к машине за час, все три ноды
  # видят новый адрес панели, девять запросов подписок от пяти живых
  # пользователей уже с новой машины. Снимок конфигурации панели лежит в
  # docs/panel-snapshot-2026-07-30.md, дамп базы — в backups/.
  #
  # htz-hel-02 удалён в Hetzner ещё раньше; описание убрано, чтобы apply
  # не поднял его заново. Ноды Remnawave разворачиваются на машинах
  # провайдеров, до которых дотягивается DPI — см. docs/dpi/.
}
