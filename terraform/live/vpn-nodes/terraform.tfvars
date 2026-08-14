# Секретов здесь нет: cloudflare_api_token приходит из variable set проекта
# cloud-lab в HCP, как и в стеке hhh-sto-02.

cloudflare_zone_id = "1c6c22b9c953bcffffa5aec356eb547e"

# Адреса сверены с ansible/inventory/cloud.yml и подтверждены по ssh
# 15.08.2026. Все три — HostHatch, по одному ядру EPYC.
nodes = {
  "hhh-sto-01" = {
    ipv4_address = "167.104.104.131"
    country_code = "SE"
  }
  "hhh-ams-01" = {
    ipv4_address = "85.155.190.66"
    country_code = "NL"
  }
  "hhh-osl-01" = {
    ipv4_address = "91.190.155.237"
    country_code = "NO"
  }
}
