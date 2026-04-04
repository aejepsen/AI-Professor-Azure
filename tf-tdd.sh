#!/usr/bin/env bash
# =============================================================================
# tf-tdd.sh — Ciclo TDD do Terraform
# Executa as etapas em ordem e para imediatamente se qualquer uma falhar.
# Uso: ./tf-tdd.sh
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

step() { echo -e "\n${YELLOW}▶ $1${NC}"; }
ok()   { echo -e "${GREEN}✔ $1${NC}"; }
fail() { echo -e "${RED}✘ $1${NC}"; exit 1; }

step "ETAPA 1a — terraform fmt (verifica formatação)"
docker compose run --rm terraform-fmt \
  && ok "Formatação ok" \
  || fail "Arquivos .tf mal formatados. Rode: docker compose run --rm terraform fmt -recursive"

step "ETAPA 1b — terraform init (baixa providers — necessário para validate)"
docker compose run --rm terraform init \
  && ok "Init ok" \
  || fail "Falha no init — verificar credenciais Azure e acesso ao Storage Account"

step "ETAPA 1c — terraform validate (verifica sintaxe e referências)"
docker compose run --rm terraform-validate \
  && ok "Validação ok" \
  || fail "Erros de sintaxe ou referências inválidas nos arquivos .tf"

step "ETAPA 2 — terraform plan (mostra o que será criado)"
# -detailed-exitcode: 0=sem mudanças, 2=mudanças presentes, 1=erro real
set +e
docker compose run --rm terraform-plan
PLAN_EXIT=$?
set -e
if [ "$PLAN_EXIT" -eq 0 ] || [ "$PLAN_EXIT" -eq 2 ]; then
  ok "Plan ok — revise o output acima antes de aplicar"
else
  fail "Plan falhou — corrigir erros antes de prosseguir"
fi

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  TDD Terraform concluído com sucesso!${NC}"
echo -e "${GREEN}  Para aplicar: docker compose run --rm terraform-apply${NC}"
echo -e "${GREEN}  Para Terratest: cd infra/terratest && go test -v -timeout 30m${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
