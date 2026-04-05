# AI Professor v1 — Execution Plan

> Versão: 1.1 | Data: 2026-04-05 (atualizado após implementação)
> Sequência de implementação com critérios de aceite por fase.
> **Regra**: só avançar de fase quando todos os critérios de aceite da fase anterior forem cumpridos.

---

## FASE 0 — SETUP E PRÉ-REQUISITOS ✅ CONCLUÍDA
**Objetivo**: ambiente de desenvolvimento 100% funcional antes de escrever qualquer linha de negócio.

### 0.1 Repositório e estrutura base

- [x] Clonar/criar repositório `AI-Professor-Azure`
- [x] Criar estrutura de diretórios conforme Action Plan §11.1
- [x] Configurar `.gitignore` (`.env`, `__pycache__`, `node_modules`)
- [x] Criar `README.md` com instruções de setup local
- [x] Configurar `pre-commit` hooks: `black`, `isort`, `mypy`, `pytest`

### 0.2 Ambiente Python (backend)

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn langgraph anthropic qdrant-client \
            python-jose[cryptography] httpx pydantic-settings \
            structlog pytest pytest-asyncio pytest-cov \
            azure-storage-blob==12.20.0 assemblyai==0.59.0 \
            fastembed sentence-transformers
pip freeze > requirements.txt
```

### 0.3 Ambiente Node (frontend)

```bash
npm install -g @angular/cli@17
ng new frontend --standalone --routing --style=scss
cd frontend
npm install @azure/msal-browser marked
```

### Critérios de aceite — Fase 0
- [x] `python -c "import fastapi, langgraph, anthropic, qdrant_client"` sem erros
- [x] `ng version` retorna Angular 17
- [x] `git status` limpo, `.env` não rastreado
- [ ] `terraform version` retorna >= 1.5.0

---

## FASE 1 — INFRAESTRUTURA AZURE ⚠️ PARCIALMENTE CONCLUÍDA
**Objetivo**: toda a infraestrutura provisionada como código, reproduzível.

> **Status**: recursos criados via `az cli` (workaround para agilizar o desenvolvimento). Migração para Terraform é um requisito pendente — nenhum recurso deve permanecer fora do IaC em produção final.

### 1.1 App Registrations (PRIORITÁRIO — sem isso nada funciona)

```bash
# Via az cli (Terraform azuread provider também funciona)
# App Reg FRONTEND (SPA)
az ad app create \
  --display-name "ai-professor-frontend" \
  --sign-in-audience "AzureADMyOrg" \
  --spa-redirect-uris "https://{STATIC_WEB_APP_URL}"

# App Reg API BACKEND
az ad app create \
  --display-name "ai-professor-api" \
  --sign-in-audience "AzureADMyOrg"

# Expor escopo no App Reg API
az ad app update --id {API_APP_ID} \
  --set api.oauth2PermissionScopes='[{
    "id": "{UUID-NOVO}",
    "adminConsentDescription": "Permite acesso à API",
    "adminConsentDisplayName": "access_as_user",
    "isEnabled": true,
    "type": "User",
    "userConsentDescription": "Permite acesso à API",
    "userConsentDisplayName": "access_as_user",
    "value": "access_as_user"
  }]'

# Configurar accessTokenAcceptedVersion = 2
az ad app update --id {API_APP_ID} \
  --set api.requestedAccessTokenVersion=2
```

### 1.2 Terraform — módulos a criar

**`infra/terraform/main.tf`** — recursos principais:
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  # Backend remoto obrigatório (Storage Account Azure ou Terraform Cloud)
  backend "azurerm" {
    resource_group_name  = "tf-state-rg"
    storage_account_name = "aiprofessortfstate"
    container_name       = "tfstate"
    key                  = "ai-professor-prod.tfstate"
  }
}

module "container_app_env" { ... }
module "container_app_backend" { ... }
module "static_web_app" { ... }
module "acr" { ... }
```

**Recursos obrigatórios**:
- Resource Group: `ai-professor-prod-rg`
- Azure Container Registry (ACR): para imagens Docker
- Container Apps Environment: networking compartilhado
- Container App (backend): com secrets configurados via Terraform
- Static Web App: para frontend Angular
- Storage Account: estado do Terraform

### 1.3 Secrets no Container App via Terraform

```hcl
resource "azurerm_container_app" "backend" {
  # ...
  secret {
    name  = "anthropic-key"
    value = var.anthropic_api_key  # Vem de terraform.tfvars (não commitado)
  }
  secret {
    name  = "qdrant-url"
    value = var.qdrant_url
  }
  # ... demais secrets

  template {
    container {
      env {
        name        = "ANTHROPIC_API_KEY"
        secret_name = "anthropic-key"
      }
      # ... demais env vars referenciando secrets
    }
  }
}
```

### 1.4 Workflow de deploy da infra

```bash
cd infra/terraform
terraform fmt
terraform validate
terraform plan -out=tfplan -var-file="prod.tfvars"  # prod.tfvars no .gitignore
terraform apply tfplan
```

### Critérios de aceite — Fase 1
- [ ] `terraform apply` sem erros (migração dos recursos para IaC — **pendente**)
- [ ] Todos os recursos declarados no Terraform (Container App, Static Web App, Blob Storage, App Registrations)
- [ ] Terraform state remoto configurado (Storage Account Azure)
- [x] Container App provisionado e Running (`ai-professor-backend`, 2 CPU / 4Gi, min_replicas=0)
- [x] Container App tem todas as env vars configuradas via secrets
- [x] Static Web App provisionado: `https://jolly-cliff-0e7c4130f.1.azurestaticapps.net`
- [x] App Registrations criados com escopo `access_as_user` visível no portal
- [x] Azure Blob Storage provisionado: conta `aiprofessorstorage`, container `uploads`, CORS configurado
- [x] Qdrant Cloud collection `ai_professor_docs` com vetores dense (multilingual-e5-large) e sparse (BM25)

> URLs de produção:
> - Frontend: `https://jolly-cliff-0e7c4130f.1.azurestaticapps.net`
> - Backend: `https://ai-professor-backend.bluedesert-c198f5d7.eastus.azurecontainerapps.io`

---

## FASE 2 — BACKEND: TDD E IMPLEMENTAÇÃO ✅ CONCLUÍDA
**Objetivo**: backend funcionando com cobertura ≥80%, todos os testes verdes.

### 2.1 Ordem de implementação (TDD — teste primeiro)

#### 2.1.1 Core Config (sem testes, apenas setup)

```python
# backend/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    qdrant_url: str
    qdrant_api_key: str
    azure_tenant_id: str
    azure_client_id: str
    ragas_test_token: str
    # Adicionados para Azure Blob Storage + AssemblyAI
    azure_storage_account_name: str
    azure_storage_account_key: str
    azure_storage_container: str = "uploads"
    assemblyai_api_key: str

    class Config:
        env_file = ".env"

settings = Settings()
```

#### 2.1.2 Auth Middleware (CRÍTICO — TDD obrigatório)

**Escrever testes ANTES:**

```python
# backend/tests/unit/test_auth.py

# Teste 1: token válido deve passar
def test_valid_jwt_passes():
    ...

# Teste 2: token expirado deve retornar 401
def test_expired_jwt_returns_401():
    ...

# Teste 3: audience errado deve retornar 401
def test_wrong_audience_returns_401():
    ...

# Teste 4: issuer errado deve retornar 401
def test_wrong_issuer_returns_401():
    ...

# Teste 5: token sem Bearer prefix deve retornar 401
def test_missing_bearer_returns_401():
    ...

# Teste 6: RAGAS token fixo deve passar em /eval endpoints
def test_ragas_token_passes_eval_endpoint():
    ...
```

**Depois implementar:**

```python
# backend/api/auth.py
import httpx
from jose import jwt, JWTError
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

JWKS_URL = "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())
) -> dict:
    """
    Valida JWT do Azure Entra ID (tokens v2).

    Valida:
    - Assinatura via JWKS público da Microsoft
    - audience = {AZURE_CLIENT_ID}  ← GUID bare (NÃO "api://...")
    - issuer   = https://login.microsoftonline.com/{TENANT_ID}/v2.0
    - expiração

    Raises:
        HTTPException 401: token inválido ou expirado
    """
    token = credentials.credentials
    try:
        jwks = await _get_jwks()
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.azure_client_id,   # GUID bare
            issuer=f"https://login.microsoftonline.com/{settings.azure_tenant_id}/v2.0"
        )
        return claims
    except JWTError as e:
        raise HTTPException(status_code=401, detail=str(e))
```

> **Crítico**: `accessTokenAcceptedVersion = 2` no App Reg API faz os tokens terem `aud = GUID bare` e `iss = .../v2.0`. Usar essas strings exatas na validação.

#### 2.1.3 KnowledgeService (TDD)

```python
# Testes: busca retorna resultados, query vazia retorna [], Qdrant down retorna erro tratado
# Implementar: busca híbrida BM25 + dense, conexão com retry
```

#### 2.1.4 ChatService (TDD)

```python
# Testes: streaming funciona, contexto vazio gera resposta "não encontrado", erro Anthropic tratado
# Implementar: generate_stream com Claude Sonnet, SSE
```

#### 2.1.5 LangGraph Agent (TDD)

```python
# Testes: graph compila, query simples retorna resposta, estados de erro tratados
# Implementar: StateGraph com nodes retrieve → generate
```

#### 2.1.6 API Endpoints (TDD de integração)

```python
# Testes: POST /chat/stream com JWT válido retorna SSE 200
#          POST /chat/stream sem JWT retorna 401
#          POST /chat/stream com JWT de audiência errada retorna 401
#          GET  /health retorna {"status": "ok"}
#          GET  /eval/search com RAGAS token retorna resultados
```

### 2.2 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Dependências separadas para aproveitar cache de layers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY . .

# Usuário não-root (segurança)
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Critérios de aceite — Fase 2
- [x] `pytest --cov=. --cov-report=term` → cobertura ≥ 80%
- [x] Todos os cenários de JWT testados (válido, expirado, audience errado, issuer errado)
- [x] `docker build -t ai-professor-backend .` sem erros
- [x] `docker run --env-file .env ai-professor-backend` sobe sem erros
- [x] `curl localhost:8000/health` retorna `{"status": "ok"}`
- [x] Testes de integração passam com variáveis de storage mockadas no `conftest.py`

---

## FASE 3 — FRONTEND: MSAL CORRETO DESDE O INÍCIO ✅ CONCLUÍDA
**Objetivo**: Angular com MSAL configurado, login funcionando, serviço de chat com Bearer token.

### 3.1 MSAL — configuração implementada

```typescript
// src/app/app.config.ts  (standalone, sem NgModules)

// MSAL usa @azure/msal-browser (NÃO @azure/msal-angular — versão standalone)
// Cache em localStorage + handleRedirectPromise() no construtor do AppComponent
// Sem MsalInterceptor — token adquirido manualmente via acquireTokenSilent() no ApiService

const msalConfig: Configuration = {
  auth: {
    clientId: environment.frontendClientId,
    authority: `https://login.microsoftonline.com/${environment.tenantId}`,
    redirectUri: window.location.origin,
  },
  cache: { cacheLocation: 'localStorage' },
};
```

> **Implementação real**: sem `@azure/msal-angular` — usamos `@azure/msal-browser` diretamente. Token adquirido com `acquireTokenSilent()` no `ApiService` e adicionado manualmente no header `Authorization`. MSAL não é usado como interceptor HTTP.

### 3.2 CSP no `staticwebapp.config.json`

```json
{
  "navigationFallback": {
    "rewrite": "/index.html",
    "exclude": ["/api/*"]
  },
  "globalHeaders": {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://{API_URL} https://login.microsoftonline.com https://graph.microsoft.com https://{TENANT_ID}.b2clogin.com; frame-src https://login.microsoftonline.com; img-src 'self' data:"
  },
  "routes": [
    {
      "route": "/api/*",
      "allowedRoles": ["authenticated"]
    }
  ]
}
```

### 3.3 ApiService — SSE com Bearer token

```typescript
// src/app/services/api.service.ts

// SSE implementado com fetch + ReadableStream (NÃO EventSource — não suporta headers custom)
// Token adquirido com acquireTokenSilent() antes de cada chamada
// Sem NgRx — estado gerenciado diretamente nos componentes com signals/properties

streamChat(query: string, token: string): Observable<string> {
  return new Observable(observer => {
    fetch(`${environment.apiUrl}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ query })
    }).then(response => {
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      const pump = () => reader.read().then(({ done, value }) => {
        if (done) { observer.complete(); return; }
        // Parse SSE: "data: {...}\n\n"
        const text = decoder.decode(value);
        // extrai campo "text" de cada evento
        observer.next(text);
        pump();
      });
      pump();
    });
  });
}
```

> **Nota**: NgRx não foi utilizado — arquitetura simplificada com componentes standalone e estado local. SSE via `fetch` + `ReadableStream`, não `EventSource`.

### Critérios de aceite — Fase 3
- [x] `ng build --configuration production` sem erros
- [x] Login Microsoft funciona no browser (redirect flow)
- [x] Bearer token é enviado corretamente para `/chat/stream`
- [x] SSE streaming funciona no browser (mensagem aparece token a token)
- [x] `marked` renderiza Markdown nas respostas do Claude

---

## FASE 4 — PIPELINE DE INGEST VIA BLOB STORAGE ✅ CONCLUÍDA
**Objetivo**: usuários fazem upload de vídeo direto ao Azure Blob, backend transcreve via AssemblyAI e indexa no Qdrant.

### 4.1 Serviços implementados

**`backend/services/blob_service.py`** — gerencia SAS tokens:
```python
class BlobService:
    def generate_upload_sas(self, filename: str) -> tuple[str, str]:
        # retorna (upload_url_com_sas_write_2h, blob_name)

    def get_read_url(self, blob_name: str) -> str:
        # retorna URL com SAS de leitura (4h) para AssemblyAI

    def delete_blob(self, blob_name: str) -> None:
        # deleta após processamento
```

**`backend/services/ingest_service.py`** — transcrição e indexação:
```python
def ingest_from_url(self, url: str, filename: str) -> dict[str, Any]:
    # 1. AssemblyAI transcreve via URL SAS
    # 2. Chunking do texto transcrito
    # 3. Upsert no Qdrant (dense + sparse vectors)
    # 4. Retorna metadados (chunks_indexed, duration_s)

def _transcribe_url(self, url: str, filename: str) -> tuple[str, float]:
    config = aai.TranscriptionConfig(
        speech_models=["universal-2"],  # SDK 0.59.0+, lista obrigatória
        language_code="pt",
    )
    transcriber = aai.Transcriber(config=config)
    transcript = transcriber.transcribe(url)
```

### 4.2 Endpoints de ingest

```python
GET  /ingest/sas-token?filename=xxx  → {upload_url, blob_name}
POST /ingest/process {blob_name, original_filename}  → {job_id}  (imediato)
GET  /ingest/status/{job_id}  → {status: "processing"|"done"|"error", ...}
```

### 4.3 Frontend — IngestComponent

```typescript
// Fluxo: fase 'upload' (XHR PUT com progress) → fase 'processing' (polling 5s)
// ChangeDetectorRef.detectChanges() obrigatório nos callbacks (fora da Angular zone)
// Estimativa de tempo: duração do vídeo via <video> element / 3 / 60 (universal-2 ≈ 3x real-time)
// Barra de progresso animada durante processamento (incremento linear até 95%)
```

### 4.4 Fontes dinâmicas no RAG

`KnowledgeService.list_sources()` + injeção no system prompt garante que Claude liste os tópicos disponíveis dinamicamente sem hardcode.

### Critérios de aceite — Fase 4
- [x] Upload de vídeo ≤ 670MB funciona com barra de progresso
- [x] AssemblyAI transcreve em português via URL SAS
- [x] Chunks indexados no Qdrant com vetores dense + sparse
- [x] Blob deletado após processamento bem-sucedido
- [x] Frontend mostra progresso de upload (0→100%) e estimativa de tempo de processamento
- [x] Fontes indexadas aparecem dinamicamente nas respostas do Claude
- [x] Vídeos indexados: PCD_AULA_8.mkv (7 chunks), Análise Estatística Espacial I.mkv (90 chunks), Introdução ao SQL e PostgreSQL.mkv (3 chunks)

---

## FASE 5 — CI/CD COMPLETO ✅ CONCLUÍDA
**Objetivo**: pipeline automatizado separando deploy de backend e frontend.

### 5.1 Estrutura real do `cd.yml`

```yaml
name: CD — AI Professor

on:
  push:
    branches: [main]

jobs:
  # JOB 0: Detecta quais partes do repo mudaram
  changes:
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      frontend: ${{ steps.filter.outputs.frontend }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            backend:
              - 'backend/**'
            frontend:
              - 'frontend/**'

  # JOB 1: Testes do backend (só se backend mudou)
  test:
    needs: changes
    if: needs.changes.outputs.backend == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests/ --cov=backend --cov-fail-under=80

  # JOB 2: Build + Push imagem Docker para GHCR (não ACR)
  build-push:
    needs: [changes, test]
    if: needs.changes.outputs.backend == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Login GHCR
        run: echo "${{ secrets.GHCR_TOKEN }}" | docker login ghcr.io -u "${{ secrets.GHCR_USERNAME }}" --password-stdin
      - name: Build e Push
        run: |
          docker build -t ghcr.io/${{ secrets.GHCR_USERNAME }}/ai-professor-backend:${{ github.sha }} ./backend
          docker push ghcr.io/${{ secrets.GHCR_USERNAME }}/ai-professor-backend:${{ github.sha }}

  # JOB 3: Deploy Container App (só se backend mudou)
  deploy:
    needs: [changes, build-push]
    if: needs.changes.outputs.backend == 'true'
    runs-on: ubuntu-latest
    steps:
      - name: Azure Login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      - name: Deploy Container App
        run: |
          az containerapp update \
            --name ${{ secrets.CONTAINER_APP_NAME }} \
            --resource-group ${{ secrets.RESOURCE_GROUP }} \
            --image ghcr.io/${{ secrets.GHCR_USERNAME }}/ai-professor-backend:${{ github.sha }}

  # JOB 4: Deploy Frontend (só se frontend mudou — NÃO reinicia o backend)
  frontend-deploy:
    needs: changes
    if: needs.changes.outputs.frontend == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cd frontend && npm ci && npm run build -- --configuration production
      - uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_API_TOKEN }}
          action: "upload"
          app_location: "frontend"
          output_location: "dist/frontend/browser"
```

> **Decisão crítica**: `dorny/paths-filter` separa os jobs de backend e frontend. Um push de CSS não reinicia o Container App, preservando background tasks (ingest) em andamento.

### 5.2 RAGAS evaluation script

```python
# evaluation/ragas_eval.py
# Conjunto de perguntas de teste com respostas esperadas
# Chama /eval/search e /chat/eval
# Claude Haiku como juiz avalia: faithfulness, relevancy, recall, precision
# Retorna exit(0) se média >= THRESHOLD, exit(1) caso contrário
# Imprime tabela detalhada por pergunta
THRESHOLD = 0.55
```

### Critérios de aceite — Fase 5
- [x] Push para `main` dispara pipeline automaticamente
- [x] Job de testes falha se cobertura < 80% (sem avançar para build)
- [x] Deploy do backend só ocorre quando arquivos em `backend/**` mudam
- [x] Deploy do frontend só ocorre quando arquivos em `frontend/**` mudam
- [x] Imagem Docker publicada no GHCR (ghcr.io), não ACR
- [x] Nenhum secret visível nos logs do CI

---

## FASE 6 — TESTE END-TO-END ✅ CONCLUÍDA
**Objetivo**: fluxo completo usuário → login → chat → resposta funcionando.

### 6.1 Roteiro de teste manual

1. Abrir `https://jolly-cliff-0e7c4130f.1.azurestaticapps.net` no browser
2. Clicar em "Entrar com Microsoft"
3. Fazer login com conta do tenant `d0900507-73c9-42c3-a8bf-a8eabdd611d8`
4. Verificar que login redireciona de volta ao app
5. Digitar: **"Quais assuntos você pode me ajudar?"**
6. Verificar que Claude lista os vídeos indexados (SQL, Análise Espacial, PCD)
7. Digitar: **"O que é o comando SELECT em SQL?"**
8. Verificar que a resposta aparece em streaming com contexto do vídeo de SQL
9. Digitar: **"O que é análise estatística espacial?"**
10. Verificar resposta baseada no vídeo de Análise Estatística Espacial
11. Abrir DevTools → Network → verificar:
    - Request para `/chat/stream` tem `Authorization: Bearer {token}`
    - Token decodificado tem `aud = 087f139e-7252-49cf-ab70-abb64eac8667` (GUID bare)
    - Response tem `Content-Type: text/event-stream`

### 6.2 Teste de segurança

```bash
# Sem token → deve retornar 401
curl -X POST {API_URL}/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
# Esperado: {"detail": "..."}  HTTP 401

# Token do Graph API (audience errado) → deve retornar 401
# Token expirado → deve retornar 401
```

### 6.3 Monitoramento pós-deploy

```bash
# Health check
curl {API_URL}/health
# Esperado: {"status": "ok", "qdrant": "connected", "anthropic": "reachable"}

# Métricas
curl {API_URL}/metrics
```

### Critérios de aceite — Fase 6
- [x] Login Microsoft funciona end-to-end
- [x] Chat responde com contexto correto dos vídeos indexados
- [x] Streaming funciona (tokens aparecem progressivamente)
- [x] Request sem token retorna 401
- [x] Claude lista dinamicamente os assuntos disponíveis
- [x] Upload de vídeo funciona com barra de progresso e estimativa de tempo

---

## RESUMO DE RISCOS E MITIGAÇÕES

| Risco | Probabilidade | Mitigação |
|---|---|---|
| JWT audience errado (mesmo erro da v1) | Alta | Testar unitariamente 5 cenários de JWT antes de qualquer deploy |
| CSP bloqueando MSAL | Alta | Configurar CSP no dia 1, testar login antes de implementar chat |
| Secrets perdidos entre deploys | Alta | 100% Terraform com secrets declarados — nunca az cli manual |
| RAGAS score abaixo do threshold | Média | Rodar RAGAS localmente antes de fazer PR para main |
| Container App sem memória suficiente | Baixa | Definir CPU/Mem no Terraform, monitorar métricas após deploy |
| Qdrant Cloud fora do ar | Baixa | Health check expõe status, retry policy no KnowledgeService |
| Rate limit Anthropic | Baixa | Exponential backoff no ChatService, error handling na UI |

---

## CHECKLIST FINAL PRÉ-PRODUÇÃO

- [x] Nenhum secret em código ou logs
- [x] Container App com scale-to-zero (min_replicas=0)
- [x] CI/CD com path-filter para não reiniciar backend em changes de frontend
- [x] Blob deletado após processamento (sem dados desnecessários)
- [ ] **Terraform**: toda a infraestrutura migrada para IaC (requisito pendente)
- [ ] RAGAS score produção ≥ 0.70 (avaliação formal pendente)
- [ ] Backup da Qdrant collection documentado
- [ ] Runbook de incidents criado
- [ ] Documentação de onboarding de novos usuários

---

## LIÇÕES APRENDIDAS (2026-04-04 a 2026-04-05)

| Problema | Causa | Solução |
|---|---|---|
| JWT `audience` errado | Azure v2 tokens têm `aud` = GUID bare, não `api://...` | Usar GUID bare e issuer `.../v2.0` |
| Upload timeout/crash em 670MB | `@azure/storage-blob` SDK com bug em `onProgress` no browser | XHR nativo com `upload.onprogress` |
| Container restart matava jobs | CD pipeline redeploya backend em todo push | `dorny/paths-filter` separa backend/frontend |
| Progress bar não aparecia | Callbacks fora da Angular zone | `ChangeDetectorRef.detectChanges()` |
| AssemblyAI "speech_models error" | SDK 0.30.0 não suporta `speech_models` plural | Upgrade para assemblyai==0.59.0 |
| PCD_AULA_8 sumia da listagem | Busca semântica não recuperava chunks para meta-perguntas | `list_sources()` injetado no system prompt |
| CORS duplicado no Blob Storage | `az storage cors add` executado duas vezes | `cors clear` antes de `cors add` |
