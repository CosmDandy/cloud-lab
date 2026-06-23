# Role: `vpn_tuning`

Идемпотентный server-tuning для VPN-нод (RemnaWave + Xray-core): BBR + fq, увеличенные TCP/UDP буферы, `tcp_notsent_lowat`, TFO, file-descriptor лимиты, conntrack.

Значения соответствуют рекомендациям из `docs/dpi-report-22-06-26.md` (Phase 1) и заменяют статический sysctl-блок из `terraform/cloud-init/vpn.yaml.tftpl`, который применялся однократно при provisioning Hetzner-серверов. Для нод, развёрнутых вручную через Mivocloud (`miv-chi-01`, `miv-ldn-01`), эта роль — единственный путь применить тюнинг.

## Что делает

- `tasks/sysctl.yaml` — `modprobe tcp_bbr`, `/etc/modules-load.d/bbr.conf`, через `ansible.posix.sysctl` пишет все значения в `/etc/sysctl.d/99-vpn-tuning.conf` с `reload: true`
- `tasks/limits.yaml` — `community.general.pam_limits` для `* soft/hard nofile = 1048576`, плюс `DefaultLimitNOFILE` в `/etc/systemd/system.conf` (с `systemctl daemon-reexec` через handler)

## Переменные

См. `defaults/main.yaml`:
- `vpn_tuning_sysctl` — словарь sysctl-параметров (override через `group_vars/host_vars`)
- `vpn_tuning_nofile_limit` — лимит дескрипторов (по умолчанию `1048576`)
- `vpn_tuning_sysctl_file` — путь файла (по умолчанию `/etc/sysctl.d/99-vpn-tuning.conf`)

## Использование

```yaml
# ansible/playbooks/vpn-node-tune.yml
- hosts: vpn_nodes
  become: true
  roles:
    - vpn_tuning
```

```bash
ansible-lint ansible/roles/vpn_tuning/
ansible-playbook ansible/playbooks/vpn-node-tune.yml --syntax-check
ansible-playbook ansible/playbooks/vpn-node-tune.yml -l miv-ldn-01 --check --diff
ansible-playbook ansible/playbooks/vpn-node-tune.yml -l miv-ldn-01
```

## Verification

После apply:
```bash
ssh root@<node> '
  sysctl net.ipv4.tcp_congestion_control net.core.default_qdisc \
         net.core.rmem_max fs.file-max net.ipv4.tcp_notsent_lowat'
# bbr / fq / 67108864 / 2097152 / 131072

# В новой сессии:
ssh root@<node> 'ulimit -n'  # ≥ 1048576
```

## Совместимость

- Ubuntu 22.04 / 24.04 LTS
- Требует коллекций: `ansible.posix`, `community.general`
- Conntrack-параметры применяются только при загруженном `nf_conntrack` модуле (на VPN-нодах с Docker — всегда)
