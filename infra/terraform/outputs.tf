# =============================================================================
# Outputs — valores necessários para CI/CD e configuração do frontend
# =============================================================================

output "container_app_url" {
  description = "URL pública do backend (Container App)"
  value       = "https://${azurerm_container_app.backend.ingress[0].fqdn}"
}

output "static_web_app_url" {
  description = "URL do frontend (Static Web App)"
  value       = "https://${azurerm_static_web_app.frontend.default_host_name}"
}

output "static_web_app_api_key" {
  description = "Token de deploy do Static Web App (usar como GitHub Secret)"
  value       = azurerm_static_web_app.frontend.api_key
  sensitive   = true
}

output "api_app_registration_client_id" {
  description = "Client ID do App Registration da API (AZURE_CLIENT_ID no backend)"
  value       = azuread_application.api.client_id
}

output "frontend_app_registration_client_id" {
  description = "Client ID do App Registration do Frontend (FRONTEND_CLIENT_ID no build Angular)"
  value       = azuread_application.frontend.client_id
}

output "resource_group_name" {
  description = "Nome do Resource Group principal"
  value       = azurerm_resource_group.main.name
}

output "container_app_name" {
  description = "Nome do Container App (para az containerapp update no CI/CD)"
  value       = azurerm_container_app.backend.name
}
