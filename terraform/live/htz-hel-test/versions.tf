terraform {
  required_version = ">= 1.10"

  # Проект заводится в UI до первого init: терраформ создаёт воркспейс сам,
  # но проект ожидает уже существующим. Воркспейсы здесь — по машине на
  # каждый, общий у них только проект и его variable set; общего стейта нет
  # намеренно, иначе apply ради одной DNS-записи трогал бы всю инфраструктуру.
  cloud {
    organization = "CosmDandy"
    workspaces {
      name    = "htz-hel-test"
      project = "cloud-lab"
    }
  }

  # GitHub-провайдера здесь нет намеренно: секреты стенда живут в SOPS,
  # а не в окружениях репозитория. Побочный выигрыш — просроченный PAT,
  # на котором сейчас падает план vpn-infra, этому root'у не мешает.
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.60"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
