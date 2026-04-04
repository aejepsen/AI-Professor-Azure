#!/bin/sh
# =============================================================================
# Wrapper para terraform no container
# Copia apenas os arquivos JSON de auth do ~/.azure do host para um diretório
# local — o msal_http_cache.bin (pickle binário) fica separado por versão
# =============================================================================
mkdir -p /tmp/azure-config

# Arquivos de auth necessários (JSON — compatíveis entre versões de az cli)
for f in azureProfile.json msal_token_cache.json clouds.config; do
  if [ -f "/root/.azure-host/${f}" ]; then
    cp "/root/.azure-host/${f}" /tmp/azure-config/
  fi
done

export AZURE_CONFIG_DIR=/tmp/azure-config
exec terraform "$@"
