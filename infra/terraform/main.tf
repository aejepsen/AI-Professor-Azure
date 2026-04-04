# =============================================================================
# AI Professor v1 — Infraestrutura Azure
# =============================================================================
# Princípio: 100% Terraform — nenhum recurso criado manualmente via az cli
# ghcr.io usado como container registry (gratuito, sem ACR)
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "ai-professor-tfstate-rg"
    storage_account_name = "aiprofessortfstate"
    container_name       = "tfstate"
    key                  = "ai-professor-prod.tfstate"
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

provider "azuread" {
  tenant_id = var.tenant_id
}

locals {
  tags = {
    project     = "ai-professor"
    environment = var.environment
    managed_by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# Resource Group principal
# -----------------------------------------------------------------------------
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}
