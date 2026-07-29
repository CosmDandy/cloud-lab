# ══════════════════════════════════════════════
# Unified servers (Remnawave architecture)
#
# Секреты и переменные окружения GitHub, из которых deploy-control.yml
# собирает .env панели. Половина живёт до переезда Remnawave на роль
# panel: пока панель развёрнута старой схемой, это единственный путь
# её обновить, и убирать его раньше нового нельзя.
#
# random_password ниже хранят действующие секреты работающей панели —
# те же значения лежат в .env на машине. Удаление ресурса стирает
# единственную читаемую копию: в GitHub секреты write-only.
# ══════════════════════════════════════════════

resource "github_repository_environment" "server" {
  for_each    = var.servers
  repository  = var.github_repository
  environment = each.key
}

resource "random_password" "jwt_auth_secret" {
  for_each = local.control_servers
  length   = 64
  special  = false
}

resource "random_password" "jwt_api_tokens_secret" {
  for_each = local.control_servers
  length   = 64
  special  = false
}

resource "random_password" "postgres_password" {
  for_each = local.control_servers
  length   = 32
  special  = false
}

resource "random_password" "cookie_secret" {
  for_each = local.control_servers
  length   = 32
  special  = false
}

resource "random_password" "metrics_pass" {
  for_each = local.control_servers
  length   = 32
  special  = false
}

locals {
  control_env_secrets = {
    for name, _ in local.control_servers : name => {
      JWT_AUTH_SECRET       = random_password.jwt_auth_secret[name].result
      JWT_API_TOKENS_SECRET = random_password.jwt_api_tokens_secret[name].result
      POSTGRES_PASSWORD     = random_password.postgres_password[name].result
      COOKIE_SECRET         = random_password.cookie_secret[name].result
      METRICS_PASS          = random_password.metrics_pass[name].result
    }
  }

  control_flat_secrets = merge([
    for server, secrets in local.control_env_secrets : {
      for key, value in secrets :
      "${server}/${key}" => {
        environment = server
        key         = key
        value       = value
      }
    }
  ]...)
}

resource "github_actions_environment_secret" "server" {
  for_each        = local.control_flat_secrets
  repository      = var.github_repository
  environment     = each.value.environment
  secret_name     = each.value.key
  plaintext_value = each.value.value

  depends_on = [github_repository_environment.server]
}

resource "github_actions_environment_variable" "server_address" {
  for_each      = var.servers
  repository    = var.github_repository
  environment   = each.key
  variable_name = "SERVER_ADDRESS"
  value         = local.server_fqdn[each.key]

  depends_on = [github_repository_environment.server]
}

resource "github_actions_environment_variable" "server_ipv4" {
  for_each      = var.servers
  repository    = var.github_repository
  environment   = each.key
  variable_name = "SERVER_IPV4"
  value         = module.server[each.key].ipv4_address

  depends_on = [github_repository_environment.server]
}

resource "github_actions_environment_variable" "server_acme_email" {
  for_each      = var.servers
  repository    = var.github_repository
  environment   = each.key
  variable_name = "ACME_EMAIL"
  value         = var.acme_email

  depends_on = [github_repository_environment.server]
}

resource "github_actions_environment_variable" "panel_domain" {
  for_each      = local.control_servers
  repository    = var.github_repository
  environment   = each.key
  variable_name = "PANEL_DOMAIN"
  value         = "vpn.${var.domain}"

  depends_on = [github_repository_environment.server]
}

resource "github_actions_environment_variable" "mesh_domain" {
  for_each      = local.control_servers
  repository    = var.github_repository
  environment   = each.key
  variable_name = "MESH_DOMAIN"
  value         = "mesh.${var.domain}"

  depends_on = [github_repository_environment.server]
}

resource "github_actions_environment_variable" "traefik_domain" {
  for_each      = local.control_servers
  repository    = var.github_repository
  environment   = each.key
  variable_name = "TRAEFIK_DOMAIN"
  value         = "traefik.${var.domain}"

  depends_on = [github_repository_environment.server]
}

resource "github_actions_environment_variable" "sub_domain" {
  for_each      = local.control_servers
  repository    = var.github_repository
  environment   = each.key
  variable_name = "SUB_DOMAIN"
  value         = "sub.${var.domain}"

  depends_on = [github_repository_environment.server]
}

# ══════════════════════════════════════════════
# Node SSL certificates (generated from Panel)
# ══════════════════════════════════════════════

