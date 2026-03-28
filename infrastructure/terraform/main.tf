# infrastructure/terraform/main.tf
# Provisionamento completo da infraestrutura Azure para o AI Professor

terraform {
  required_version = ">= 1.8.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.52"
    }
  }
  backend "azurerm" {
    resource_group_name  = "ai-professor-tfstate-rg"
    storage_account_name = "aiprofessortfstate"
    container_name       = "tfstate"
    key                  = "ai-professor.tfstate"
  }
}

provider "azurerm" {
  features {}
}

variable "environment" {
  default = "prod"
}

variable "location" {
  default = "eastus"
}

variable "tenant_id" {}

variable "client_id" {}

locals {
  prefix = "ai-professor-${var.environment}"
  tags = {
    project     = "ai-professor"
    environment = var.environment
    managed-by  = "terraform"
  }
}

# ── Resource Group ────────────────────────────────────────────────────────────
resource "azurerm_resource_group" "main" {
  name     = "${local.prefix}-rg"
  location = var.location
  tags     = local.tags
}

# ── Qdrant Cloud (vector store externo — gratuito ate 1GB) ────────────────────
# Nao provisionado via Terraform — configurado via variavel de ambiente
# Criar conta gratuita em: https://cloud.qdrant.io
# Copiar a URL do cluster e a API Key para o .env e secrets do GitHub

# ── Azure OpenAI (Embeddings) ─────────────────────────────────────────────────
resource "azurerm_cognitive_account" "openai" {
  name                = "${local.prefix}-openai"
  resource_group_name = azurerm_resource_group.main.name
  location            = "swedencentral"
  kind                = "OpenAI"
  sku_name            = "S0"
  tags                = local.tags
}

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = "text-embedding-3-large"
  cognitive_account_id = azurerm_cognitive_account.openai.id
  model {
    format  = "OpenAI"
    name    = "text-embedding-3-large"
    version = "1"
  }
  scale {
    type     = "Standard"
    capacity = 120
  }
}

# ── Blob Storage ──────────────────────────────────────────────────────────────
resource "azurerm_storage_account" "main" {
  name                     = replace("${local.prefix}storage", "-", "")
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  tags                     = local.tags
}

resource "azurerm_storage_container" "videos" {
  name                  = "videos"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "documents" {
  name                  = "documents"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "transcriptions" {
  name                  = "transcriptions"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

# ── Azure Speech Service ──────────────────────────────────────────────────────
resource "azurerm_cognitive_account" "speech" {
  name                = "${local.prefix}-speech"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  kind                = "SpeechServices"
  sku_name            = "S0"
  tags                = local.tags
}

# ── Container Registry (backend Docker) ──────────────────────────────────────
resource "azurerm_container_registry" "main" {
  name                = replace("${local.prefix}acr", "-", "")
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = local.tags
}

# ── Container Apps Environment ────────────────────────────────────────────────
resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.prefix}-logs"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 90
  tags                = local.tags
}

resource "azurerm_container_app_environment" "main" {
  name                       = "${local.prefix}-cae"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = local.tags
}

# ── Container App — Backend FastAPI ──────────────────────────────────────────
resource "azurerm_container_app" "backend" {
  name                         = "${local.prefix}-backend"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  secret {
    name  = "azure-client-secret"
    value = "PLACEHOLDER_CLIENT_SECRET"
  }

  secret {
    name  = "qdrant-api-key"
    value = "PLACEHOLDER_QDRANT_KEY"
  }

  secret {
    name  = "anthropic-key"
    value = "PLACEHOLDER_ANTHROPIC_KEY"
  }

  template {
    min_replicas = 1
    max_replicas = 10

    container {
      name   = "backend"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 1.0
      memory = "2Gi"

      env {
        name  = "AZURE_TENANT_ID"
        value = var.tenant_id
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = var.client_id
      }
      env {
        name        = "AZURE_CLIENT_SECRET"
        secret_name = "azure-client-secret"
      }
      env {
        name  = "QDRANT_URL"
        value = "SEU_QDRANT_CLOUD_URL"
      }
      env {
        name        = "QDRANT_API_KEY"
        secret_name = "qdrant-api-key"
      }
      env {
        name        = "ANTHROPIC_API_KEY"
        secret_name = "anthropic-key"
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = azurerm_cognitive_account.openai.endpoint
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

# ── Static Web App — Angular Frontend ────────────────────────────────────────
resource "azurerm_static_web_app" "frontend" {
  name                = "${local.prefix}-frontend"
  resource_group_name = azurerm_resource_group.main.name
  location            = "eastus2"
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}

# ── Application Insights ──────────────────────────────────────────────────────
resource "azurerm_application_insights" "main" {
  name                = "${local.prefix}-appinsights"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  retention_in_days   = 90
  tags                = local.tags
}

# ── Outputs ───────────────────────────────────────────────────────────────────
output "frontend_url" {
  value = "https://${azurerm_static_web_app.frontend.default_host_name}"
}

output "backend_url" {
  value = "https://${azurerm_container_app.backend.latest_revision_fqdn}"
}

output "storage_account" {
  value = azurerm_storage_account.main.name
}

output "appinsights_key" {
  value     = azurerm_application_insights.main.instrumentation_key
  sensitive = true
}
