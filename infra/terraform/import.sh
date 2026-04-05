#!/usr/bin/env bash
# =============================================================================
# terraform import — mapeia recursos existentes (criados via az cli) para o state
# Executar dentro de infra/terraform/ com prod.tfvars preenchido
# =============================================================================
set -e

SUB="subscriptions/8ab458d3-deb7-4124-99c0-860e83350c19"
RG="/$SUB/resourceGroups/ai-professor-prod-rg"

echo "==> Resource Group"
terraform import -var-file=prod.tfvars \
  azurerm_resource_group.main \
  "$RG"

echo "==> Log Analytics Workspace"
terraform import -var-file=prod.tfvars \
  azurerm_log_analytics_workspace.main \
  "$RG/providers/Microsoft.OperationalInsights/workspaces/ai-professor-logs"

echo "==> Container Apps Environment"
terraform import -var-file=prod.tfvars \
  azurerm_container_app_environment.main \
  "$RG/providers/Microsoft.App/managedEnvironments/ai-professor-env"

echo "==> Container App (backend)"
terraform import -var-file=prod.tfvars \
  azurerm_container_app.backend \
  "$RG/providers/Microsoft.App/containerApps/ai-professor-backend"

echo "==> Static Web App (frontend)"
terraform import -var-file=prod.tfvars \
  azurerm_static_web_app.frontend \
  "$RG/providers/Microsoft.Web/staticSites/ai-professor-frontend"

echo "==> Storage Account"
terraform import -var-file=prod.tfvars \
  azurerm_storage_account.uploads \
  "$RG/providers/Microsoft.Storage/storageAccounts/aiprofessorstorage"

echo "==> Storage Container"
terraform import -var-file=prod.tfvars \
  azurerm_storage_container.uploads \
  "https://aiprofessorstorage.blob.core.windows.net/uploads"

echo "==> App Registration — API"
terraform import -var-file=prod.tfvars \
  azuread_application.api \
  "/applications/aa89645c-82c1-4165-acff-e8ac2610b602"

echo "==> App Registration — API identifier URI"
terraform import -var-file=prod.tfvars \
  azuread_application_identifier_uri.api \
  "aa89645c-82c1-4165-acff-e8ac2610b602/api://087f139e-7252-49cf-ab70-abb64eac8667"

echo "==> Service Principal — API"
terraform import -var-file=prod.tfvars \
  azuread_service_principal.api \
  "3fa9cb5c-9fc5-4703-84b2-3cd4faf27b8d"

echo "==> App Registration — Frontend"
terraform import -var-file=prod.tfvars \
  azuread_application.frontend \
  "/applications/aa1159a4-7332-4f82-b561-4cab1ecf0682"

echo "==> Service Principal — Frontend"
terraform import -var-file=prod.tfvars \
  azuread_service_principal.frontend \
  "ca019f32-90f5-4ffc-ab1c-c702398ec69c"

echo ""
echo "✓ Import concluído. Rode: terraform plan -var-file=prod.tfvars"
