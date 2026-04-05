# =============================================================================
# Azure Blob Storage — uploads de vídeo para transcrição AssemblyAI
# CORS configurado para Static Web App + localhost:4200
# Blobs são deletados pelo backend após processamento
# =============================================================================

resource "azurerm_storage_account" "uploads" {
  name                              = "aiprofessorstorage"
  resource_group_name               = azurerm_resource_group.main.name
  location                          = azurerm_resource_group.main.location
  account_tier                      = "Standard"
  account_replication_type          = "LRS"
  allow_nested_items_to_be_public   = false
  cross_tenant_replication_enabled  = false
  min_tls_version                   = "TLS1_2"
  tags                              = local.tags

  blob_properties {
    cors_rule {
      allowed_headers    = ["*"]
      allowed_methods    = ["GET", "PUT", "DELETE", "OPTIONS"]
      allowed_origins = [
        "https://${azurerm_static_web_app.frontend.default_host_name}",
        "http://localhost:4200",
      ]
      exposed_headers    = ["*"]
      max_age_in_seconds = 3600
    }
  }
}

resource "azurerm_storage_container" "uploads" {
  name                  = "uploads"
  storage_account_name  = azurerm_storage_account.uploads.name
  container_access_type = "private"
}
