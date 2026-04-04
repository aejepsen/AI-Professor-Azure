# =============================================================================
# Static Web App — Frontend Angular 17
# Free tier: 100 GB bandwidth/mês, SSL automático, deploy via GitHub Actions
# =============================================================================

resource "azurerm_static_web_app" "frontend" {
  name                = "ai-professor-frontend"
  resource_group_name = azurerm_resource_group.main.name
  location            = "eastus2" # Static Web Apps disponível em eastus2
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}
