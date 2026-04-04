# =============================================================================
# Variáveis — valores sensíveis vêm de prod.tfvars (não commitado)
# =============================================================================

variable "subscription_id" {
  description = "Azure Subscription ID"
  type        = string
}

variable "tenant_id" {
  description = "Azure Tenant ID"
  type        = string
}

variable "resource_group_name" {
  description = "Nome do Resource Group principal"
  type        = string
  default     = "ai-professor-prod-rg"
}

variable "location" {
  description = "Região Azure"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Ambiente (prod, staging)"
  type        = string
  default     = "prod"
}

# --- Secrets do backend ---

variable "anthropic_api_key" {
  description = "Chave da API Anthropic (Claude)"
  type        = string
  sensitive   = true
}

variable "qdrant_url" {
  description = "URL do Qdrant Cloud"
  type        = string
  sensitive   = true
}

variable "qdrant_api_key" {
  description = "API Key do Qdrant Cloud"
  type        = string
  sensitive   = true
}

variable "ragas_test_token" {
  description = "Token fixo para endpoints /eval no pipeline RAGAS"
  type        = string
  sensitive   = true
}

variable "assemblyai_api_key" {
  description = "API Key do AssemblyAI para transcrição de áudio"
  type        = string
  sensitive   = true
}

# --- Container App ---

variable "container_image" {
  description = "Imagem Docker do backend (ghcr.io/usuario/ai-professor:tag)"
  type        = string
  default     = "ghcr.io/aejepsen/ai-professor-backend:latest"
}

variable "ghcr_username" {
  description = "Username GitHub para autenticar no ghcr.io"
  type        = string
}

variable "ghcr_token" {
  description = "GitHub PAT com permissão read:packages para o Container App puxar a imagem"
  type        = string
  sensitive   = true
}
