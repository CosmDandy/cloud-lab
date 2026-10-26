# Role: `vpn_tuning`

Идемпотентный server-tuning для VPN-нод (RemnaWave + Xray-core): BBR + fq, увеличенные TCP/UDP буферы, `tcp_notsent_lowat`, TFO, file-descriptor лимиты, conntrack.

Значения соответствуют рекомендациям из `docs/dpi/report-2026-06-22.md` (Phase 1). Целевые машины — три ноды HostHatch (`hhh-ams-01`, `hhh-osl-01`, `hhh-sto-01`) из группы `vpn_nodes`: контейнер `remnanode` на них развёрнут вне репозитория, и эта роль — единственное, чем ими управляет Ansible.

## Что делает

- `tasks/sysctl.yaml` — `modprobe tcp_bbr`, `/etc/modules-load.d/bbr.conf`, через `ansible.posix.sysctl` пишет все значения в `/etc/sysctl.d/99-vpn-tuning.conf` с `reload: true`, и закрывает корневой qdisc с двух сторон: `net.core.default_qdisc` действует только на интерфейсы, поднятые после его установки, поэтому одним sysctl не обойтись ни на живой машине, ни после ребута
  - `vpn-tuning-qdisc.service` — `Type=oneshot` после `network-online.target`, ставит qdisc на загрузке. Без него после каждой перезагрузки интерфейс возвращается к `pfifo_fast`, потому что systemd-networkd поднимает его раньше, чем systemd-sysctl читает `/etc/sysctl.d`
  - задача `tc qdisc replace` — правит текущее состояние живой машины, где юнит с `RemainAfterExit=yes` второй раз не сработает
- `tasks/limits.yaml` — `community.general.pam_limits` для `* soft/hard nofile = 1048576`, плюс `DefaultLimitNOFILE` в `/etc/systemd/system.conf` (с `systemctl daemon-reexec` через handler)

## Переменные

См. `defaults/main.yaml`:
- `vpn_tuning_sysctl` — словарь sysctl-параметров (override через `group_vars/host_vars`)
- `vpn_tuning_nofile_limit` — лимит дескрипторов (по умолчанию `1048576`)
- `vpn_tuning_sysctl_file` — путь файла (по умолчанию `/etc/sysctl.d/99-vpn-tuning.conf`)
- `vpn_tuning_qdisc_unit`, `vpn_tuning_iface`, `vpn_tuning_tc_path` — имя юнита, интерфейс (по умолчанию дефолтный из фактов) и абсолютный путь к `tc`: systemd не ищет бинарь в `PATH`

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
# bbr / fq / 67108864 / 2097152 / 131072 / 4194304 / 0
# и корневой qdisc — fq, а не pfifo_fast

# Юнит, который вернёт fq после перезагрузки:
ssh root@<node> 'systemctl is-enabled vpn-tuning-qdisc; systemctl is-active vpn-tuning-qdisc'
# enabled / active

# Проверка без ребута — сбить qdisc и дать юниту его вернуть:
ssh root@<node> '
  tc qdisc replace dev eth0 root pfifo_fast
  systemctl restart vpn-tuning-qdisc
  tc qdisc show dev eth0 | head -1'   # снова fq

# В новой сессии:
ssh root@<node> 'ulimit -n'  # ≥ 1048576
```

## Совместимость

- Ubuntu 22.04 / 24.04 LTS
- Требует коллекций: `ansible.posix`, `community.general`
- Conntrack-параметры применяются только при загруженном `nf_conntrack` модуле (на VPN-нодах с Docker — всегда)
