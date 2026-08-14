# Вход в Proxmox через Pocket ID

Кластер `pve-kvt-l` (три ноды, 192.168.20.151–153, PVE 9.2.10) пускает по SSO
из Pocket ID. Realm называется `pocketid`, заведён 07.08.2026.

Машины кластера живут в домашней сети и ролями Ansible не управляются —
репозиторий описывает только клиента в Pocket ID, а realm на кластере заводится
руками. Ниже — что где лежит и как это повторить.

## Что в репозитории

`ansible/inventory/host_vars/hhh-sto-02/main.yml`:

- `proxmox_oidc_client_id` — идентификатор клиента;
- запись `proxmox` в `oidc_clients` с шестью callback-адресами.

Секрет — `proxmox_oidc_client_secret` в `secrets.sops.yaml` рядом.

Клиента создаёт роль `oidc`; заводить его руками в UI нельзя — при следующем
прогоне роль этого не увидит, а на чистом Pocket ID клиента просто не окажется.
Ровно так однажды отвалился вход в gatus.

```bash
cd ansible
ansible-playbook -i inventory/cloud.yml playbooks/site.yml -l hhh-sto-02 --tags oidc
```

**`--check` для нового клиента не проходит и это нормально.** В режиме проверки
задача создания пропускается, а следующая — «Read state of declared OIDC
clients» — получает 404 на ещё не существующего клиента. Первый прогон только
боевой; секрет роль печатает один раз, его нужно положить в SOPS и прогнать
роль ещё раз (второй прогон даёт `changed=0`).

## Почему шесть callback-адресов

Proxmox **не имеет настройки redirect URI** — он собирает адрес из того, по
которому пришёл браузер, и подставляет в запрос. Поэтому в клиенте перечислены
все адреса, по которым к кластеру обращаются: три IP и три имени `.local` из
сертификатов нод.

```
https://192.168.20.151:8006      https://pve-kvt-l-01.local:8006
https://192.168.20.152:8006      https://pve-kvt-l-02.local:8006
https://192.168.20.153:8006      https://pve-kvt-l-03.local:8006
```

Зайдёте с четвёртой ноды или через новое имя — Pocket ID отвергнет redirect,
пока адрес не добавлен в `callback_urls`.

## Realm на кластере

`/etc/pve/domains.cfg` синхронизируется по кластеру автоматически — команда
выполняется на любой одной ноде.

```bash
pveum realm add pocketid --type openid \
  --issuer-url https://oidc.cosmdandy.dev \
  --client-id <proxmox_oidc_client_id> \
  --client-key <секрет из SOPS> \
  --username-claim username \
  --autocreate 1 \
  --scopes "email profile" \
  --comment "Pocket ID SSO"
```

Тонкости, каждая из которых стоила отдельного захода:

- **`--scopes "email profile"`, без `openid`.** PVE добавляет `openid` сам; если
  указать его явно, в запросе окажется `scope=openid+openid+email+profile`.
- **Секрет нельзя передать в том же heredoc, что и скрипт.** `sops | ssh
  'bash -s' <<'EOF'` — пайп и heredoc делят один stdin, секрет склеивается с
  первой строкой скрипта, `read` не срабатывает, и realm создаётся с пустым
  `client-key`, молча. Правильно — двумя шагами: доставить секрет во временный
  файл (`umask 077; cat > /root/.pid-secret`), затем
  `pveum realm modify pocketid --client-key "$(cat /root/.pid-secret)"` и
  `shred -u`.
- **PKCE включён с обеих сторон.** PVE всегда шлёт `code_challenge_method=S256`,
  роль `oidc` по умолчанию создаёт клиента с `pkce_enabled: true`. Выключать
  PKCE на клиенте (как пришлось для gatus и Remnawave) здесь не нужно.
- **`--username-claim username`** — пользователь получает имя из
  `preferred_username`, то есть входит как `<логин>@pocketid`.

## Права

`--autocreate 1` заводит пользователя при первом входе, но **без единого
права** — залогиниться получится, а интерфейс будет пустым. Права выдаются
отдельно:

```bash
pveum user add cosmdandy@pocketid --comment "Pocket ID SSO"
pveum acl modify / --users cosmdandy@pocketid --roles Administrator
```

Вход ограничен группой `admins` в Pocket ID (`group_restricted: true`), так что
посторонний не пройдёт даже при наличии учётной записи в Pocket ID.

## Проверка без браузера

Строит ли PVE корректный запрос к провайдеру:

```bash
pvesh create /access/openid/auth-url --realm pocketid \
  --redirect-url "https://192.168.20.151:8006"
```

В URL должны совпасть `client_id`, `redirect_uri` и присутствовать
`code_challenge`. Ошибка здесь означает проблему в realm, а не в браузере.

## Откат

```bash
pveum realm delete pocketid
```

Realm `pam` и `pve` не затрагиваются — вход по паролю продолжает работать
всё время, включая период настройки.
