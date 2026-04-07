# =============================================================================
# Container Apps — Log Analytics + Environment + Container App (backend)
# Consumption plan: serverless, scale-to-zero, dentro do free grant Azure
# Imagem: ghcr.io (sem ACR, sem custo adicional)
# =============================================================================

# -----------------------------------------------------------------------------
# Log Analytics Workspace (obrigatório para Container Apps Environment)
# Primeiros 5 GB/mês são gratuitos
# -----------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "main" {
  name                = "ai-professor-logs"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30 # Mínimo do SKU PerGB2018
  tags                = local.tags
}

# -----------------------------------------------------------------------------
# Container Apps Environment — Consumption (serverless)
# -----------------------------------------------------------------------------
resource "azurerm_container_app_environment" "main" {
  name                       = "ai-professor-env"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = local.tags
}

# -----------------------------------------------------------------------------
# Container App — Backend FastAPI
# Todos os secrets via secret block (nunca env var direta com valor sensível)
# -----------------------------------------------------------------------------
resource "azurerm_container_app" "backend" {
  name                         = "ai-professor-backend"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  # Credenciais ghcr.io para puxar a imagem privada
  registry {
    server               = "ghcr.io"
    username             = var.ghcr_username
    password_secret_name = "ghcr-token"
  }

  # Secrets — valores nunca expostos como env vars diretas
  secret {
    name  = "ghcr-token"
    value = var.ghcr_token
  }
  secret {
    name  = "anthropic-key"
    value = var.anthropic_api_key
  }
  secret {
    name  = "qdrant-url"
    value = var.qdrant_url
  }
  secret {
    name  = "qdrant-api-key"
    value = var.qdrant_api_key
  }
  secret {
    name  = "azure-tenant-id"
    value = var.tenant_id
  }
  secret {
    name  = "azure-client-id"
    value = azuread_application.api.client_id
  }
  secret {
    name  = "ragas-test-token"
    value = var.ragas_test_token
  }
  secret {
    name  = "assemblyai-key"
    value = var.assemblyai_api_key
  }
  secret {
    name  = "storage-account-name"
    value = azurerm_storage_account.uploads.name
  }
  secret {
    name  = "storage-account-key"
    value = azurerm_storage_account.uploads.primary_access_key
  }
  secret {
    name  = "storage-container"
    value = azurerm_storage_container.uploads.name
  }

  template {
    min_replicas = 0 # scale-to-zero → custo zero quando inativo
    max_replicas = 2

    container {
      name   = "backend"
      image  = var.container_image
      cpu    = 0.5
      memory = "2Gi"

      # Env vars referenciam secrets — valores nunca em texto claro
      env {
        name        = "ANTHROPIC_API_KEY"
        secret_name = "anthropic-key"
      }
      env {
        name        = "QDRANT_URL"
        secret_name = "qdrant-url"
      }
      env {
        name        = "QDRANT_API_KEY"
        secret_name = "qdrant-api-key"
      }
      env {
        name        = "AZURE_TENANT_ID"
        secret_name = "azure-tenant-id"
      }
      env {
        name        = "AZURE_CLIENT_ID"
        secret_name = "azure-client-id"
      }
      env {
        name        = "RAGAS_TEST_TOKEN"
        secret_name = "ragas-test-token"
      }
      env {
        name        = "ASSEMBLYAI_API_KEY"
        secret_name = "assemblyai-key"
      }
      env {
        name        = "AZURE_STORAGE_ACCOUNT_NAME"
        secret_name = "storage-account-name"
      }
      env {
        name        = "AZURE_STORAGE_ACCOUNT_KEY"
        secret_name = "storage-account-key"
      }
      env {
        name        = "AZURE_STORAGE_CONTAINER"
        secret_name = "storage-container"
      }

      liveness_probe {
        transport = "HTTP"
        path      = "/health"
        port      = 8000
      }

      readiness_probe {
        transport = "HTTP"
        path      = "/health"
        port      = 8000
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}
