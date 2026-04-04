# AI Professor v1 — Action Plan

> Versão: 1.0 | Data: 2026-03-30
> Objetivo: eliminar todos os bloqueios técnicos e entregar um sistema RAG corporativo production-ready.

---

## 1. PRINCÍPIOS FUNDADORES

| Princípio | Regra |
|---|---|
| **Infrastructure as Code** | 100% Terraform — nenhum recurso criado manualmente via `az cli` |
| **TDD First** | Testes escritos antes do código de produção em todo o backend |
| **Auth Correto desde o Início** | Dois App Registrations separados, escopos e audiences corretos antes de qualquer linha de código |
| **Secrets nunca em código** | Todas as credenciais via GitHub Secrets + Container App Secrets |
| **Desacoplamento por contrato** | Cada camada se comunica por interfaces bem definidas |
| **Observabilidade obrigatória** | Logs estruturados, métricas RAGAS e health checks em todos os serviços |

---

## 2. ARQUITETURA TARGET

```
┌─────────────────────────────────────────────────────────────────┐
│                        AZURE (eastus)                           │
│                                                                 │
│  ┌──────────────────┐        ┌─────────────────────────────┐   │
│  │  Static Web App  │        │      Container Apps Env      │   │
│  │  Angular 17      │◄──────►│                             │   │
│  │  (MSAL + NgRx)   │  HTTPS │  ┌─────────────────────┐   │   │
│  └──────────────────┘  + JWT │  │   FastAPI Backend    │   │   │
│                              │  │   (uvicorn/gunicorn) │   │   │
│  ┌──────────────────┐        │  └──────────┬──────────┘   │   │
│  │  Azure Entra ID  │        │             │               │   │
│  │  ┌────────────┐  │        │  ┌──────────▼──────────┐   │   │
│  │  │ App Reg FE │  │        │  │   LangGraph Agent    │   │   │
│  │  └────────────┘  │        │  │   (StateGraph)       │   │   │
│  │  ┌────────────┐  │        │  └──────────┬──────────┘   │   │
│  │  │ App Reg API│  │        │             │               │   │
│  │  └────────────┘  │        │  ┌──────────▼──────────┐   │   │
│  └──────────────────┘        │  │  KnowledgeService    │   │   │
│                              │  │  (Qdrant hybrid)     │   │   │
│  ┌──────────────────┐        │  └─────────────────────┘   │   │
│  │  ACR             │        └─────────────────────────────┘   │
│  │  Docker Images   │                                           │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────▼──────────────┐
                    │        EXTERNOS              │
                    │  Qdrant Cloud (us-east-1)    │
                    │  Anthropic API               │
                    └──────────────────────────────┘
```

---

## 3. AUTENTICAÇÃO — MAPA COMPLETO

### 3.1 Fluxo de autenticação end-to-end

```
Usuário
  │
  ▼ (1) Login Microsoft
Azure Entra ID ──► Token MSAL (escopo: api://{API_CLIENT_ID}/access_as_user)
  │
  ▼ (2) Bearer Token no header Authorization
Frontend Angular
  │
  ▼ (3) POST /chat/stream  Authorization: Bearer <jwt>
FastAPI Backend
  │
  ▼ (4) Valida JWT
  │   audience  = api://{API_CLIENT_ID}/access_as_user  ✓
  │   issuer    = https://sts.windows.net/{TENANT_ID}/  ✓
  │   signature = chaves públicas JWKS da Microsoft      ✓
  │
  ▼ (5) Autorizado → executa LangGraph
  │
  ▼ (6) API Key no header
Anthropic API (Claude Sonnet)
  │
  ▼ (7) API Key no header
Qdrant Cloud
```

### 3.2 App Registrations obrigatórios

| App Registration | Tipo | Configuração Crítica |
|---|---|---|
| `ai-professor-frontend` | SPA | `redirectUri` = URL do Static Web App, `implicitFlow` = false |
| `ai-professor-api` | Web/API | Expor escopo `access_as_user`, `accessTokenAcceptedVersion` = 2 |

### 3.3 Regra de ouro JWT

```
Token gerado pelo frontend → escopo api://{API_CLIENT_ID}/access_as_user
Backend valida:
  - aud = api://{API_CLIENT_ID}/access_as_user   (NÃO "00000003-..." do Graph)
  - iss = https://sts.windows.net/{TENANT_ID}/
  - exp > now()
  - assinatura via JWKS endpoint da Microsoft
```

---

## 4. VARIÁVEIS DE AMBIENTE — CONTRATO DE CONFIGURAÇÃO

### 4.1 Container App (backend) — todos via secrets

| Env Var | Secret Name | Quem usa |
|---|---|---|
| `ANTHROPIC_API_KEY` | `anthropic-key` | ChatService |
| `QDRANT_URL` | `qdrant-url` | KnowledgeService |
| `QDRANT_API_KEY` | `qdrant-api-key` | KnowledgeService |
| `AZURE_TENANT_ID` | `azure-tenant-id` | Auth middleware |
| `AZURE_CLIENT_ID` | `azure-client-id` | Auth middleware (= API App Registration client ID) |
| `RAGAS_TEST_TOKEN` | `ragas-test-token` | /eval endpoints |

### 4.2 Static Web App (frontend) — build-time apenas

| Var | Onde fica | Valor |
|---|---|---|
| `FRONTEND_CLIENT_ID` | GitHub Secret → build Angular | Client ID do App Reg Frontend |
| `API_CLIENT_ID` | GitHub Secret → build Angular | Client ID do App Reg API |
| `TENANT_ID` | GitHub Secret → build Angular | Tenant ID Azure |
| `API_URL` | GitHub Secret → build Angular | URL do Container App |

### 4.3 GitHub Actions CI/CD

| Secret | Uso |
|---|---|
| `AZURE_CREDENTIALS` | Service Principal para deploy (escopo mínimo) |
| `ACR_LOGIN_SERVER` | Azure Container Registry URL |
| `CONTAINER_APP_NAME` | Nome do Container App |
| `RESOURCE_GROUP` | `ai-professor-prod-rg` |
| `ANTHROPIC_API_KEY` | RAGAS Quality Gate no CI |
| `QDRANT_URL` | RAGAS Quality Gate no CI |
| `QDRANT_API_KEY` | RAGAS Quality Gate no CI |
| `RAGAS_TEST_TOKEN` | RAGAS Quality Gate no CI |

---

## 5. SEGURANÇA

### 5.1 Princípio do menor privilégio

- Service Principal do CI/CD: apenas `AcrPush` no ACR + `Contributor` no Resource Group
- Container App Managed Identity: sem permissões desnecessárias no Azure AD
- Qdrant: API Key com permissão apenas na collection `ai_professor_docs`

### 5.2 CSP obrigatório no `staticwebapp.config.json`

```json
{
  "globalHeaders": {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' {API_URL} https://login.microsoftonline.com https://graph.microsoft.com; frame-src https://login.microsoftonline.com; img-src 'self' data:"
  }
}
```

### 5.3 Segredos no pipeline

- **NUNCA** usar `-var` inline no `terraform apply` com valores sensíveis
- Usar `-var-file` com arquivo `.tfvars` que não entra no repositório
- GitHub Secrets para valores sensíveis no CI/CD
- Arquivo `.env` no `.gitignore`

### 5.4 Validação de inputs

- Backend valida todos os inputs com Pydantic v2
- Query máxima: 1000 caracteres
- Rate limiting no Container App (via DAPR ou middleware FastAPI)

---

## 6. DESACOPLAMENTO E ARQUITETURA LIMPA

### 6.1 Camadas do backend

```
api/          → HTTP (FastAPI): recebe requisição, valida JWT, retorna resposta SSE
agents/       → Orquestração (LangGraph): lógica de fluxo, sem I/O direto
services/     → Integração (Qdrant, Anthropic): chamadas externas isoladas
models/       → Contratos (Pydantic): schemas compartilhados entre camadas
```

### 6.2 Regras de dependência

- `api` depende de `agents` e `models` — nunca de `services` diretamente
- `agents` depende de `services` e `models` — nunca de `api`
- `services` depende somente de `models` e bibliotecas externas
- Injeção de dependência via `Depends()` do FastAPI para testabilidade

### 6.3 Contratos de serviço (interfaces)

```python
# Cada serviço expõe uma interface clara
class KnowledgeServiceProtocol(Protocol):
    async def search(self, query: str, top_k: int) -> list[SearchResult]: ...

class ChatServiceProtocol(Protocol):
    async def generate_stream(self, query: str, context: list[str]) -> AsyncGenerator[str, None]: ...
```

---

## 7. CÓDIGO LIMPO E COMENTÁRIOS

### 7.1 Regras de código

- Funções com uma responsabilidade única (SRP)
- Máximo 50 linhas por função — se passar, extrair
- Nomes de variáveis em inglês, descritivos (sem `tmp`, `data`, `obj`)
- Type hints obrigatórios em todas as funções Python
- `mypy --strict` no CI

### 7.2 Comentários — quando e como

```python
# BOM: explica o "porquê", não o "o quê"
# Azure retorna iss com trailing slash apenas em v1 tokens;
# remover para garantir compatibilidade com ambas as versões
issuer = token_claims["iss"].rstrip("/")

# RUIM: parafraseia o código
# converte para minúsculas
text = text.lower()
```

- Docstrings em classes e funções públicas (Google style)
- Comentários `# TODO:` com ticket/issue linkado
- Seções complexas (ex: validação JWT) com bloco explicativo de contexto

### 7.3 Angular — TypeScript

- `strict: true` no `tsconfig.json`
- Sem `any` — usar `unknown` + type guard quando necessário
- Componentes standalone, sem NgModules legados
- Serviços injetáveis via `providedIn: 'root'` ou `provideIn` de feature

---

## 8. PERFORMANCE

### 8.1 Backend

| Área | Estratégia |
|---|---|
| Embeddings | Cache de embeddings para queries repetidas (TTL 1h) |
| Qdrant | `prefer_grpc=True`, connection pool, batch upsert |
| Claude API | Streaming SSE direto ao cliente, sem buffer intermediário |
| FastAPI | Workers assíncronos (`asyncio`), evitar bloqueio de event loop |
| Container App | Min replicas = 1, Max = 3, CPU 0.5 / Mem 1Gi |

### 8.2 Frontend

| Área | Estratégia |
|---|---|
| Angular | `ChangeDetectionStrategy.OnPush` em todos os componentes |
| NgRx | Selectors com `createSelector` para memoização |
| SSE | ReadableStream API nativa, sem polling |
| Bundle | Lazy loading de módulos, `build --configuration production` |

### 8.3 Qdrant — busca híbrida

```python
# BM25 (keyword) + dense (semântico) → melhor recall
# Configurar dois vetores na collection:
# - "dense": embeddings Claude/OpenAI (1536-dim)
# - "sparse": BM25 via FastEmbed
```

---

## 9. GOVERNANÇA

### 9.1 Versionamento

- **Backend**: semver (`MAJOR.MINOR.PATCH`) via tag Git
- **API**: versão no path (`/v1/chat/stream`) — nunca quebrar contratos
- **Terraform**: pin de todas as versões de providers (`~> 3.x`)
- **Python deps**: `requirements.txt` com versões fixas + `pip-compile`
- **npm deps**: `package-lock.json` commitado

### 9.2 Branching

```
main          → produção (protegido, require PR + CI verde)
develop       → integração
feature/xxx   → features
fix/xxx       → bugfixes
```

### 9.3 Code review obrigatório

- Mínimo 1 aprovação para merge em `main`
- CI deve estar verde (testes + RAGAS quality gate)
- Sem `--force-push` em branches compartilhadas

---

## 10. MÉTRICAS E OBSERVABILIDADE DO MODELO

### 10.1 RAGAS — métricas de qualidade RAG

| Métrica | Descrição | Threshold CI | Threshold Prod |
|---|---|---|---|
| `faithfulness` | Resposta fiel ao contexto recuperado | 0.55 | 0.70 |
| `answer_relevancy` | Resposta relevante à pergunta | 0.55 | 0.70 |
| `context_recall` | Contexto contém a informação necessária | 0.55 | 0.70 |
| `context_precision` | Contexto não tem ruído desnecessário | 0.55 | 0.70 |
| `score_médio` | Média das 4 métricas | 0.55 | 0.70 |

### 10.2 Coleta de métricas por chamada

```python
# Cada resposta do chat deve registrar:
{
  "timestamp": "ISO8601",
  "query_length": int,
  "chunks_retrieved": int,
  "top_chunk_score": float,        # Score Qdrant do melhor chunk
  "generation_latency_ms": int,    # Tempo total até primeiro token
  "stream_duration_ms": int,       # Duração do stream completo
  "tokens_generated": int,
  "model": "claude-sonnet-4-...",
  "ragas_faithfulness": float,     # Avaliado assincronamente
  "ragas_relevancy": float
}
```

### 10.3 Health checks e alertas

```
GET /health          → status do serviço (Qdrant + Anthropic reachable)
GET /health/qdrant   → status específico do Qdrant
GET /metrics         → métricas Prometheus (latência, erros, tokens)
```

### 10.4 Logs estruturados

```python
import structlog

log = structlog.get_logger()

# Toda chamada de RAG loga:
log.info("rag.search.complete",
    query_hash=hash(query),   # NÃO logar a query (dados do usuário)
    chunks_found=len(results),
    top_score=results[0].score,
    latency_ms=elapsed
)
```

---

## 11. MANUTENIBILIDADE

### 11.1 Estrutura de diretórios final

```
ai-professor/
├── backend/
│   ├── api/
│   │   ├── main.py            # App FastAPI + routers
│   │   ├── auth.py            # Middleware JWT Entra ID
│   │   └── routers/
│   │       ├── chat.py        # POST /chat/stream (SSE)
│   │       └── eval.py        # GET /eval/search, POST /chat/eval
│   ├── agents/
│   │   └── rag_graph.py       # LangGraph StateGraph
│   ├── services/
│   │   ├── knowledge_service.py   # Qdrant hybrid search
│   │   ├── chat_service.py        # Claude Sonnet streaming
│   │   └── ingest_service.py      # Indexação de documentos
│   ├── models/
│   │   ├── chat.py            # ChatRequest, ChatResponse
│   │   ├── search.py          # SearchResult, SearchRequest
│   │   └── eval.py            # RAGASResult, EvalRequest
│   ├── core/
│   │   ├── config.py          # Settings Pydantic (lê env vars)
│   │   └── logging.py         # structlog setup
│   ├── tests/
│   │   ├── unit/              # Testes unitários por módulo
│   │   ├── integration/       # Testes de integração (Qdrant real)
│   │   └── conftest.py        # Fixtures compartilhadas
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── src/app/
│       ├── core/
│       │   ├── auth/          # MSAL config + guards
│       │   ├── services/      # ChatService, AuthService
│       │   └── store/         # NgRx (actions, reducers, effects, selectors)
│       ├── features/
│       │   ├── chat/          # Componente principal de chat
│       │   └── history/       # Histórico de conversas
│       └── shared/            # Componentes reutilizáveis
├── evaluation/
│   └── ragas_eval.py          # Quality gate CI/CD
├── infra/
│   └── terraform/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── modules/
│           ├── container_app/
│           ├── static_web_app/
│           └── entra_id/
└── .github/
    └── workflows/
        └── deploy.yml
```

### 11.2 Documentação de decisões técnicas (ADR)

Para cada decisão não óbvia, criar um arquivo `docs/adr/NNN-titulo.md` com:
- **Contexto**: por que a decisão foi necessária
- **Decisão**: o que foi escolhido
- **Consequências**: trade-offs aceitos

---

## 12. INTEGRAÇÃO ENTRE SISTEMAS — MATRIZ DE DEPENDÊNCIAS

| De | Para | Protocolo | Auth | Falha crítica? |
|---|---|---|---|---|
| Angular | FastAPI | HTTPS + SSE | Bearer JWT (Entra ID) | Sim |
| FastAPI | Qdrant Cloud | HTTPS/gRPC | API Key (header) | Sim |
| FastAPI | Anthropic API | HTTPS | API Key (header) | Sim |
| FastAPI | Azure Entra JWKS | HTTPS | Público (sem auth) | Sim |
| GitHub Actions | ACR | HTTPS | Service Principal | Deploy |
| GitHub Actions | Container Apps | HTTPS | Service Principal | Deploy |
| GitHub Actions | Static Web App | HTTPS | Service Principal | Deploy |
| RAGAS (CI) | FastAPI | HTTPS | Token fixo (`RAGAS_TEST_TOKEN`) | Qualidade |

---
