# =============================================================================
# Azure Entra ID — App Registrations
# Dois App Registrations separados: Frontend (SPA) e API (backend)
# =============================================================================

# -----------------------------------------------------------------------------
# App Registration — API (backend)
# Expõe o escopo access_as_user que o frontend solicita
# accessTokenAcceptedVersion = 2 → tokens v2 com audience api://CLIENT_ID
# -----------------------------------------------------------------------------
resource "azuread_application" "api" {
  display_name     = "ai-professor-api"
  sign_in_audience = "AzureADMyOrg"
  identifier_uris  = ["api://${azuread_application.api.client_id}"]

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      admin_consent_description  = "Permite acesso à API do AI Professor"
      admin_consent_display_name = "access_as_user"
      enabled                    = true
      id                         = "00000000-0000-0000-0000-000000000001"
      type                       = "User"
      user_consent_description   = "Permite acesso à API do AI Professor"
      user_consent_display_name  = "access_as_user"
      value                      = "access_as_user"
    }
  }
}

resource "azuread_service_principal" "api" {
  client_id = azuread_application.api.client_id
}

# -----------------------------------------------------------------------------
# App Registration — Frontend (SPA)
# Não expõe escopos — apenas consome o escopo da API
# redirect_uri configurado após Static Web App ser provisionado
# -----------------------------------------------------------------------------
resource "azuread_application" "frontend" {
  display_name     = "ai-professor-frontend"
  sign_in_audience = "AzureADMyOrg"

  single_page_application {
    redirect_uris = [
      "https://${azurerm_static_web_app.frontend.default_host_name}/",
    ]
  }

  required_resource_access {
    resource_app_id = azuread_application.api.client_id

    resource_access {
      id   = "00000000-0000-0000-0000-000000000001"
      type = "Scope"
    }
  }
}

resource "azuread_service_principal" "frontend" {
  client_id = azuread_application.frontend.client_id
}
