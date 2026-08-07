# Role: `vpn_tuning`

Идемпотентный server-tuning для VPN-нод (RemnaWave + Xray-core): BBR + fq, увеличенные TCP/UDP буферы, `tcp_notsent_lowat`, TFO, file-descriptor лимиты, conntrack.

Значения соответствуют рекомендациям из `docs/dpi/report-2026-06-22.md` (Phase 1). Целевые машины — три ноды HostHatch (`hhh-ams-01`, `hhh-osl-01`, `hhh-sto-01`) из группы `vpn_nodes`: контейнер `remnanode` на них развёрнут вне репозитория, и эта роль — единственное, чем ими управляет Ansible.

## Что делает

- `tasks/sysctl.yaml` — `modprobe tcp_bbr`, `/etc/modules-load.d/bbr.conf`, через `ansible.posix.sysctl` пишет все значения в `/etc/sysctl.d/99-vpn-tuning.conf` с `reload: true`, и отдельно применяет корневой qdisc к уже поднятому интерфейсу: `net.core.default_qdisc` действует только на интерфейсы, поднятые после его установки, поэтому на живой машине одним sysctl не обойтись
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

Дефолтный инвентарь в `ansible.cfg` — домашний `local.yml`, поэтому
`-i inventory/cloud.yml` обязателен: без него группа `vpn_nodes` не находится и
прогон завершается успехом, не сделав ничего.

```bash
cd ansible
uvx ansible-lint --profile production roles/vpn_tuning playbooks/vpn-node-tune.yml
ansible-playbook -i inventory/cloud.yml playbooks/vpn-node-tune.yml --syntax-check
ansible-playbook -i inventory/cloud.yml playbooks/vpn-node-tune.yml -l hhh-ams-01 --check --diff
ansible-playbook -i inventory/cloud.yml playbooks/vpn-node-tune.yml -l hhh-ams-01
```

## Verification

После apply:
```bash
ssh root@<node> '
  sysctl net.ipv4.tcp_congestion_control net.core.default_qdisc \
         net.core.rmem_max fs.file-max net.ipv4.tcp_notsent_lowat \
         net.core.rmem_default net.ipv4.tcp_slow_start_after_idle
  tc qdisc show dev eth0 | head -1'
# bbr / fq / 67108864 / 2097152 / 131072 / 1048576 / 0
# и корневой qdisc — fq, а не pfifo_fast

# В новой сессии:
ssh root@<node> 'ulimit -n'  # ≥ 1048576
```

## Совместимость

- Ubuntu 22.04 / 24.04 LTS
- Требует коллекций: `ansible.posix`, `community.general`
- Conntrack-параметры применяются только при загруженном `nf_conntrack` модуле (на VPN-нодах с Docker — всегда)
