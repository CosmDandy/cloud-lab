terraform {
  required_version = ">= 1.10"

  cloud {
    organization = "CosmDandy"
    workspaces {
      name    = "hhh-sto-02"
      project = "cloud-lab"
    }
  }

  # Только cloudflare: машину терраформ не создаёт. У HostHatch нет
  # провайдера, сервер заводится руками в панели, а сюда приезжает готовым
  # адресом. Ровно ради этого случая dns-record и вынесен в отдельный модуль.
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
