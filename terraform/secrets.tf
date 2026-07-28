# ══════════════════════════════════════════════
# VPN (legacy, removed in Phase 5)
# ══════════════════════════════════════════════

resource "github_repository_environment" "vpn" {
  for_each    = var.vpn_servers
  repository  = var.github_repository
  environment = "vpn-${each.key}"
}

resource "random_uuid" "vless" {
  for_each = var.vpn_servers
}

resource "random_password" "hy2" {
  for_each = var.vpn_servers
  length   = 32
  special  = false
}

resource "random_password" "salamander" {
  for_each = var.vpn_servers
  length   = 32
  special  = false
}

locals {
  vpn_env_secrets = {
    for name, _ in var.vpn_servers : name => {
      VLESS_UUID          = random_uuid.vless[name].result
      REALITY_PRIVATE_KEY = var.reality_private_key
      REALITY_SHORT_ID    = var.reality_short_id
      HY2_PASSWORD        = random_password.hy2[name].result
      SALAMANDER_PASSWORD = random_password.salamander[name].result
      WARP_PRIVATE_KEY    = var.warp_private_key
    }
  }

  vpn_flat_secrets = merge([
    for server, secrets in local.vpn_env_secrets : {
      for key, value in secrets :
      "${server}/${key}" => {
        environment = "vpn-${server}"
        key         = key
        value       = value
      }
    }
  ]...)
}

resource "github_actions_environment_secret" "vpn" {
  for_each        = local.vpn_flat_secrets
  repository      = var.github_repository
  environment     = each.value.environment
  secret_name     = each.value.key
  plaintext_value = each.value.value

  depends_on = [github_repository_environment.vpn]
}

resource "github_actions_environment_variable" "vpn_reality_public_key" {
  for_each      = var.vpn_servers
  repository    = var.github_repository
  environment   = "vpn-${each.key}"
  variable_name = "REALITY_PUBLIC_KEY"
  value         = var.reality_public_key

  depends_on = [github_repository_environment.vpn]
}

resource "github_actions_environment_variable" "vpn_server_address" {
  for_each      = var.vpn_servers
  repository    = var.github_repository
  environment   = "vpn-${each.key}"
  variable_name = "SERVER_ADDRESS"
  value         = local.vpn_fqdn[each.key]

  depends_on = [github_repository_environment.vpn]
}

resource "github_actions_environment_variable" "vpn_server_ipv4" {
  for_each      = var.vpn_servers
  repository    = var.github_repository
  environment   = "vpn-${each.key}"
  variable_name = "SERVER_IPV4"
  value         = module.vpn_server[each.key].ipv4_address

  depends_on = [github_repository_environment.vpn]
}

resource "github_actions_environment_variable" "vpn_acme_email" {
  for_each      = var.vpn_servers
  repository    = var.github_repository
  environment   = "vpn-${each.key}"
  variable_name = "ACME_EMAIL"
  value         = var.acme_email

  depends_on = [github_repository_environment.vpn]
}

resource "github_actions_environment_variable" "vpn_warp_address_v4" {
  for_each      = var.vpn_servers
  repository    = var.github_repository
  environment   = "vpn-${each.key}"
  variable_name = "WARP_ADDRESS_V4"
  value         = var.warp_address_v4

  depends_on = [github_repository_environment.vpn]
}

resource "github_actions_environment_variable" "vpn_warp_address_v6" {
  for_each      = var.vpn_servers
  repository    = var.github_repository
  environment   = "vpn-${each.key}"
  variable_name = "WARP_ADDRESS_V6"
  value         = var.warp_address_v6

  depends_on = [github_repository_environment.vpn]
}

resource "github_actions_environment_variable" "vpn_caddy_user" {
  for_each      = var.vpn_servers
  repository    = var.github_repository
  environment   = "vpn-${each.key}"
  variable_name = "CADDY_USER"
  value         = "vpn-${each.key}"

  depends_on = [github_repository_environment.vpn]
}

resource "github_actions_environment_secret" "vpn_caddy_hash" {
  for_each        = var.vpn_servers
  repository      = var.github_repository
  environment     = "vpn-${each.key}"
  secret_name     = "CADDY_HASH"
  plaintext_value = var.caddy_hash

  depends_on = [github_repository_environment.vpn]
}

# ══════════════════════════════════════════════
# Unified servers (Remnawave architecture)
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

