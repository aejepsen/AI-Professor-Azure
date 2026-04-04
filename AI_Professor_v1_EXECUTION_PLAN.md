# AI Professor v1 — Execution Plan

> Versão: 1.0 | Data: 2026-03-30
> Sequência de implementação com critérios de aceite por fase.
> **Regra**: só avançar de fase quando todos os critérios de aceite da fase anterior forem cumpridos.

---

## FASE 0 — SETUP E PRÉ-REQUISITOS
**Objetivo**: ambiente de desenvolvimento 100% funcional antes de escrever qualquer linha de negócio.

### 0.1 Repositório e estrutura base

- [ ] Clonar/criar repositório `AI-Professor-Azure`
- [ ] Criar estrutura de diretórios conforme Action Plan §11.1
- [ ] Configurar `.gitignore` (`.env`, `.terraform`, `__pycache__`, `node_modules`, `*.tfvars`)
- [ ] Criar `README.md` com instruções de setup local
- [ ] Configurar `pre-commit` hooks: `black`, `isort`, `mypy`, `pytest`

### 0.2 Ambiente Python (backend)

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn langgraph anthropic qdrant-client \
            python-jose[cryptography] httpx pydantic-settings \
            structlog pytest pytest-asyncio pytest-cov
pip freeze > requirements.txt
```

### 0.3 Ambiente Node (frontend)

```bash
npm install -g @angular/cli@17
ng new frontend --standalone --routing --style=scss
cd frontend
npm install @azure/msal-angular @azure/msal-browser @ngrx/store @ngrx/effects @ngrx/entity
```

### 0.4 Terraform — inicialização

```bash
cd infra/terraform
terraform init
```

### Critérios de aceite — Fase 0
- [ ] `python -c "import fastapi, langgraph, anthropic, qdrant_client"` sem erros
- [ ] `ng version` retorna Angular 17
- [ ] `terraform version` retorna >= 1.5.0
- [ ] `git status` limpo, `.env` não rastreado

---

## FASE 1 — INFRAESTRUTURA AZURE (TERRAFORM)
**Objetivo**: toda a infraestrutura provisionada como código, reproduzível.

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
- [ ] `terraform apply` sem erros
- [ ] `az containerapp show --name {APP} --resource-group ai-professor-prod-rg` retorna status `Running`
- [ ] Container App tem todas as env vars configuradas (verificar sem revelar valores)
- [ ] Static Web App provisionado com URL gerada
- [ ] ACR acessível para push
- [ ] App Registrations criados com escopo `access_as_user` visível no portal

---

## FASE 2 — BACKEND: TDD E IMPLEMENTAÇÃO
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
    Valida JWT do Azure Entra ID.

    Valida:
    - Assinatura via JWKS público da Microsoft
    - audience = api://{AZURE_CLIENT_ID}/access_as_user
    - issuer   = https://sts.windows.net/{TENANT_ID}/
    - expiração

    Raises:
        HTTPException 401: token inválido ou expirado
    """
    token = credentials.credentials
    try:
        # Buscar chaves públicas (cache em produção)
        jwks = await _get_jwks()
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=f"api://{settings.azure_client_id}/access_as_user",
            issuer=f"https://sts.windows.net/{settings.azure_tenant_id}/"
        )
        return claims
    except JWTError as e:
        raise HTTPException(status_code=401, detail=str(e))
```

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
- [ ] `pytest --cov=. --cov-report=term` → cobertura ≥ 80%
- [ ] Todos os cenários de JWT testados (válido, expirado, audience errado, issuer errado)
- [ ] `mypy --strict backend/` sem erros
- [ ] `docker build -t ai-professor-backend .` sem erros
- [ ] `docker run --env-file .env ai-professor-backend` sobe sem erros
- [ ] `curl localhost:8000/health` retorna `{"status": "ok"}`

---

## FASE 3 — FRONTEND: MSAL CORRETO DESDE O INÍCIO
**Objetivo**: Angular com MSAL configurado, login funcionando, serviço de chat com Bearer token.

### 3.1 MSAL — configuração completa

```typescript
// src/app/core/auth/msal.config.ts

export function MSALInstanceFactory(): IPublicClientApplication {
  return new PublicClientApplication({
    auth: {
      clientId: environment.frontendClientId,          // App Reg FRONTEND client ID
      authority: `https://login.microsoftonline.com/${environment.tenantId}`,
      redirectUri: environment.redirectUri,             // URL do Static Web App
      postLogoutRedirectUri: environment.redirectUri,
    },
    cache: {
      cacheLocation: BrowserCacheLocation.LocalStorage,
      storeAuthStateInCookie: false,                   // Evitar problemas com ITP
    },
  });
}

export function MSALGuardConfigFactory(): MsalGuardConfiguration {
  return {
    interactionType: InteractionType.Redirect,         // Redirect, não Popup (evita CSP)
    authRequest: {
      scopes: [`api://${environment.apiClientId}/access_as_user`]  // Escopo da nossa API
    }
  };
}

export function MSALInterceptorConfigFactory(): MsalInterceptorConfiguration {
  const protectedResourceMap = new Map<string, Array<string>>();
  // Só adiciona Bearer token para chamadas à nossa API
  protectedResourceMap.set(
    environment.apiUrl,
    [`api://${environment.apiClientId}/access_as_user`]
  );
  return {
    interactionType: InteractionType.Redirect,
    protectedResourceMap
  };
}
```

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

### 3.3 ChatService — SSE com Bearer token

```typescript
// src/app/core/services/chat.service.ts

@Injectable({ providedIn: 'root' })
export class ChatService {
  // MSAL Interceptor adiciona Bearer automaticamente para apiUrl
  // Usar fetch com ReadableStream para SSE (não EventSource — não suporta headers)
  streamChat(query: string): Observable<string> {
    return new Observable(observer => {
      this.authService.acquireTokenSilent({
        scopes: [`api://${environment.apiClientId}/access_as_user`]
      }).then(result => {
        fetch(`${environment.apiUrl}/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${result.accessToken}`  // Token da nossa API
          },
          body: JSON.stringify({ query })
        }).then(response => {
          const reader = response.body!.getReader();
          const decoder = new TextDecoder();

          const pump = () => reader.read().then(({ done, value }) => {
            if (done) { observer.complete(); return; }
            observer.next(decoder.decode(value));
            pump();
          });
          pump();
        });
      });
    });
  }
}
```

### 3.4 NgRx — store de chat

```
actions/chat.actions.ts   → SendMessage, MessageReceived, StreamComplete, StreamError
reducers/chat.reducer.ts  → estado: messages[], loading, error
effects/chat.effects.ts   → chama ChatService, emite actions
selectors/chat.selectors.ts → getMessages, isLoading, getError
```

### Critérios de aceite — Fase 3
- [ ] `ng build --configuration production` sem erros
- [ ] Login Microsoft funciona no browser
- [ ] Token no header tem `aud = api://{API_CLIENT_ID}/access_as_user` (verificar no Network tab)
- [ ] Bearer token é enviado corretamente para `/chat/stream`
- [ ] SSE streaming funciona no browser (mensagem aparece token a token)
- [ ] CSP sem erros no console do browser

---

## FASE 4 — INDEXAÇÃO DE DOCUMENTOS
**Objetivo**: 8 documentos indexados no Qdrant com busca híbrida funcionando.

### 4.1 Script de indexação

```bash
# Verificar collection vazia
curl "$QDRANT_URL/collections/ai_professor_docs" -H "api-key: $QDRANT_API_KEY"

# Rodar indexação
cd backend
python -m services.ingest_service
```

### 4.2 Validar indexação

```bash
# Busca de sanidade
curl -X POST "$QDRANT_URL/collections/ai_professor_docs/points/search" \
  -H "api-key: $QDRANT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"vector": [...], "limit": 3}'
```

### Critérios de aceite — Fase 4
- [ ] 8 documentos indexados (`points_count = 8` na collection info)
- [ ] Busca por "férias" retorna o Manual de Férias como top resultado
- [ ] Busca por "reembolso" retorna a Política de Reembolso como top resultado
- [ ] Latência de busca < 200ms (p99)

---

## FASE 5 — CI/CD COMPLETO
**Objetivo**: pipeline automatizado com RAGAS Quality Gate bloqueando deploys ruins.

### 5.1 Estrutura do `deploy.yml`

```yaml
name: Deploy AI Professor v2

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read
  id-token: write       # Para OIDC com Azure

jobs:
  # JOB 1: Qualidade de código
  backend-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install deps
        run: pip install -r backend/requirements.txt
      - name: Lint + Type check
        run: |
          black --check backend/
          isort --check backend/
          mypy --strict backend/
      - name: Tests + Coverage
        run: pytest backend/tests/ --cov=backend --cov-fail-under=80

  # JOB 2: Build e push imagem Docker
  build-push:
    needs: backend-quality
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Azure Login (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - name: Build e Push ACR
        run: |
          az acr build \
            --registry ${{ secrets.ACR_LOGIN_SERVER }} \
            --image ai-professor-backend:${{ github.sha }} \
            ./backend

  # JOB 3: Deploy Container App
  deploy-backend:
    needs: build-push
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Azure Login (OIDC)
        uses: azure/login@v2
        with: { ... }
      - name: Deploy Container App
        run: |
          az containerapp update \
            --name ${{ secrets.CONTAINER_APP_NAME }} \
            --resource-group ${{ secrets.RESOURCE_GROUP }} \
            --image ${{ secrets.ACR_LOGIN_SERVER }}/ai-professor-backend:${{ github.sha }}

  # JOB 4: RAGAS Quality Gate (BLOQUEIA o deploy do frontend se falhar)
  ragas-quality-gate:
    needs: deploy-backend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install RAGAS deps
        run: pip install anthropic httpx
      - name: Run RAGAS Evaluation
        env:
          API_URL: ${{ secrets.CONTAINER_APP_URL }}
          API_TEST_TOKEN: ${{ secrets.RAGAS_TEST_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python evaluation/ragas_eval.py
          # Retorna exit code != 0 se média < 0.55

  # JOB 5: Deploy Frontend
  deploy-frontend:
    needs: ragas-quality-gate    # Só deploya frontend se RAGAS passar
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Build Angular
        env:
          FRONTEND_CLIENT_ID: ${{ secrets.FRONTEND_CLIENT_ID }}
          API_CLIENT_ID: ${{ secrets.API_CLIENT_ID }}
          TENANT_ID: ${{ secrets.TENANT_ID }}
          API_URL: ${{ secrets.CONTAINER_APP_URL }}
        run: |
          cd frontend
          npm ci
          npm run build -- --configuration production
      - name: Deploy Static Web App
        uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_TOKEN }}
          action: "upload"
          app_location: "frontend"
          output_location: "dist/frontend/browser"
```

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
- [ ] Push para `main` dispara pipeline automaticamente
- [ ] Job `backend-quality` falha se cobertura < 80% (sem avançar)
- [ ] Job `ragas-quality-gate` falha se score médio < 0.55 (sem deploy do frontend)
- [ ] Deploy do backend funciona sem downtime (rolling update)
- [ ] Deploy do frontend funciona após RAGAS passar
- [ ] Nenhum secret visível nos logs do CI

---

## FASE 6 — TESTE END-TO-END
**Objetivo**: fluxo completo usuário → login → chat → resposta funcionando.

### 6.1 Roteiro de teste manual

1. Abrir URL do Static Web App no browser
2. Clicar em "Entrar com Microsoft"
3. Fazer login com conta do tenant `d0900507-...`
4. Verificar que login redireciona de volta ao app
5. Digitar: **"Como abrir um chamado no ServiceNow?"**
6. Verificar que a resposta aparece em streaming
7. Verificar que a resposta cita o Manual de TI
8. Digitar: **"Quantos dias de férias tenho por lei?"**
9. Verificar que a resposta cita a Política de Férias e menciona 30 dias
10. Abrir DevTools → Network → verificar:
    - Request para `/chat/stream` tem `Authorization: Bearer {token}`
    - Token decodificado tem `aud = api://{API_CLIENT_ID}/access_as_user`
    - Response tem `Content-Type: text/event-stream`
    - Sem erros de CSP no console

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
- [ ] Login Microsoft funciona end-to-end
- [ ] Chat responde com contexto correto dos 8 documentos
- [ ] Streaming funciona (tokens aparecem progressivamente)
- [ ] Request sem token retorna 401
- [ ] Request com token de audience errado retorna 401
- [ ] Sem erros de CSP no console
- [ ] Latência do primeiro token < 3 segundos (p95)
- [ ] RAGAS score em produção ≥ 0.70

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

- [ ] Todos os critérios de aceite das 6 fases cumpridos
- [ ] RAGAS score produção ≥ 0.70
- [ ] Nenhum secret em código ou logs
- [ ] Terraform state remoto configurado e com lock
- [ ] Backup da Qdrant collection documentado
- [ ] Runbook de incidents criado (o que fazer se backend cai, se Qdrant cai, etc.)
- [ ] Usuários criados no Azure Entra ID para teste
- [ ] Documentação de onboarding de novos usuários criada
