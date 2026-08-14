terraform {
  required_version = ">= 1.10"

  cloud {
    organization = "CosmDandy"
    workspaces {
      name    = "vpn-nodes"
      project = "cloud-lab"
    }
  }

  # Только cloudflare. Сами ноды терраформ не создаёт — они куплены в панели
  # HostHatch, провайдера у них нет. Сюда приезжают готовые адреса, отсюда
  # уезжают только имена.
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
