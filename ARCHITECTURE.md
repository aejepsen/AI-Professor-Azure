# AI Professor — Architecture

## O que é

RAG corporativo sobre vídeos: o usuário faz upload de vídeos de aula, o sistema transcreve, indexa e responde perguntas com citação de fontes. Deploy serverless no Azure, custo zero quando idle.

---

## Stack — escolhas e por que

### Backend

| Ferramenta | Versão | Por que |
|---|---|---|
| **Python 3.11** | 3.11-slim | Maturidade do ecossistema ML/AI; 3.12 ainda sem suporte em alguns pacotes críticos de embeddings |
| **FastAPI** | 0.111.0 | Melhor DX para APIs async; validação Pydantic nativa; geração de OpenAPI sem config |
| **LangGraph** | 0.0.55 | Orquestração de agente com StateGraph tipado; rollback de estado por step; mais previsível que LangChain chains |
| **Anthropic Claude** | SDK 0.26.0 | Melhor raciocínio em contexto longo; streaming nativo; custo/qualidade superior no caso de uso de RAG |
| **Qdrant** | 1.10.1 | Único que suporta hybrid search (dense + sparse BM25) numa query; payload filtering; managed cloud |
| **sentence-transformers** | 3.0.1 | `multilingual-e5-large`: melhor F1 multilíngue para português; pré-baixado na imagem (zero cold start) |
| **fastembed BM25** | 0.3.6 | Sparse embeddings leves para o componente léxico do hybrid search |
| **AssemblyAI** | 0.59.0 | WER mais baixo em fala técnica; timestamps por palavra (fontes precisas); async nativo |
| **pydantic-settings** | 2.2.1 | Config 12-factor com validação de tipos; suporte a JSON em env vars (ex: CORS_ORIGINS) |
| **structlog** | 24.1.0 | JSON logs estruturados desde o dia 1; compatível com Azure Monitor |
| **python-jose** | 3.3.0 | Validação de JWT Azure Entra ID sem SDK proprietário |

### Frontend

| Ferramenta | Versão | Por que |
|---|---|---|
| **Angular** | 17 (standalone) | Estrutura tipada para app complexo com auth; MSAL Angular oficial; SSE consumer maduro |
| **MSAL Angular** | 5.1.4 | Auth Azure Entra ID sem implementação manual de OAuth2/PKCE |
| **@azure/storage-blob** | 12.31.0 | Upload direto do browser para Azure Blob (SAS token) — backend não é gargalo de upload |
| **marked** | 17.0.6 | Rendering de markdown nas respostas do LLM |
| **Vitest** | 4.0.8 | Testes unitários mais rápidos que Jest; compatível com Vite/esbuild |

### Infraestrutura

| Ferramenta | Por que |
|---|---|
| **Azure Container Apps** | Serverless: scale-to-zero automático; consumption plan; sem Kubernetes para gerenciar |
| **Azure Static Web Apps** | CDN global incluída; build/deploy integrado com GitHub Actions; free tier |
| **Azure Entra ID** | SSO corporativo; JWT com claims customizados; sem banco de usuários para manter |
| **Azure Blob Storage** | Upload direto do browser via SAS token; custo ~$0.02/GB/mês; durabilidade 99.999999999% |
| **Qdrant Cloud** | Managed; free tier suficiente para demo; hybrid search sem infra própria |
| **Terraform** | IaC declarativo; estado remoto no Azure Storage; reproducível em qualquer conta |

---

## Arquitetura

```
Browser (Angular 17)
  │
  ├─ MSAL → Azure Entra ID (OAuth2/PKCE)
  │
  ├─ Upload ──────────────────────────────────────────► Azure Blob Storage
  │           (SAS token — backend valida, browser envia)
  │
  └─ Chat (SSE) ─────────────────────────────────────► Azure Container Apps (backend)
                                                               │
                                              ┌────────────────┼────────────────┐
                                              │                │                │
                                         Qdrant Cloud    Anthropic API    AssemblyAI
                                     (hybrid search)   (Claude Sonnet)  (transcrição)
```

### Fluxo de ingestão

```
1. Frontend → backend: solicita SAS token com scope limitado
2. Frontend → Azure Blob: upload direto (backend não processa bytes)
3. Backend: AssemblyAI transcreve (async, webhook ou polling)
4. Backend: chunking do transcript com timestamps
5. Backend: sentence-transformers → dense embeddings
6. Backend: fastembed BM25 → sparse embeddings
7. Qdrant: armazena ambos os vetores + payload (timestamps, metadata)
```

### Fluxo de chat

```
1. Browser → backend: pergunta + JWT
2. Backend: valida JWT (Azure Entra ID JWKS)
3. LangGraph: hybrid search no Qdrant (dense + BM25, re-ranking por score)
4. LangGraph: monta prompt com chunks recuperados + pergunta
5. Anthropic Claude: gera resposta com citações de fonte
6. Backend → Browser: streaming SSE (chunks em tempo real)
```

---

## Estrutura de pastas

```
.
├── backend/                   # API FastAPI + agente LangGraph
│   ├── agents/                # StateGraph (orchestration)
│   ├── api/
│   │   ├── routes/            # chat, health, ingest
│   │   ├── auth.py            # JWT validation
│   │   ├── main.py            # FastAPI app + middleware
│   │   └── schemas.py         # Pydantic models (request/response)
│   ├── services/              # Lógica de negócio (sem HTTP)
│   │   ├── blob_service.py    # Azure Blob Storage
│   │   ├── chat_service.py    # Streaming + SSE
│   │   ├── ingest_service.py  # Transcrição + chunking
│   │   └── knowledge_service.py # Qdrant hybrid search
│   ├── core/
│   │   └── config.py          # pydantic-settings (12-factor)
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── docker/            # Smoke tests pós-build
│   ├── Dockerfile             # Multi-stage: builder + runtime
│   ├── requirements-prod.txt  # Deps de produção (sem dev tools)
│   ├── requirements-test.txt  # Deps para CI (pytest, mocks)
│   └── entrypoint.sh          # Prod: sem --reload
│
├── frontend/                  # Angular 17 standalone
│   └── src/app/
│       ├── components/
│       ├── services/          # API client, Auth service
│       ├── pages/
│       └── app.config.ts      # MSAL + Azure config
│
├── infra/
│   ├── terraform/             # 100% declarativo
│   │   ├── main.tf
│   │   ├── container_app.tf
│   │   ├── blob_storage.tf
│   │   ├── entra_id.tf
│   │   └── static_web_app.tf
│   └── Dockerfile.terraform   # Terraform + Azure CLI em container
│
├── docker-compose.yml         # Terraform services (infra local)
├── docker-compose.override.yml# Backend local dev (hot-reload)
├── .env.example               # Template — nunca commitar .env
└── ARCHITECTURE.md            # Este documento
```

---

## Ports e serviços locais

| Serviço | Port | Comando |
|---|---|---|
| Backend (dev) | 8000 | `docker compose up backend` |
| Terraform | — | `docker compose run --rm terraform-plan` |

---

## Decisões de segurança

| Decisão | Razão |
|---|---|
| Multi-stage Dockerfile | Stage builder tem gcc/dev headers; stage final não — superfície de ataque mínima |
| Usuário não-root no container | PID 1 como root dá acesso desnecessário se houver escape do container |
| CORS via env var (`CORS_ORIGINS`) | URL do Static Web App muda por deploy; hardcode = redeployar backend para mudar frontend |
| SAS token com escopo limitado | Frontend nunca tem a storage account key; token expira e é escopo por container |
| JWT validation (JWKS) | Tokens Azure Entra ID validados contra JWKS público — sem estado no backend |
| `.dockerignore` em cada serviço | Impede que `.env`, `node_modules`, `.git` entrem no build context |
| `requirements-prod.txt` separado | `pytest`, `black`, `mypy` não existem na imagem de produção |

---

## Custos estimados (Azure, consumo mínimo)

| Serviço | Custo estimado |
|---|---|
| Azure Container Apps (idle) | $0 (scale-to-zero) |
| Azure Container Apps (ativo) | ~$0.000024/vCPU-s · ~$0.000003/GiB-s |
| Azure Static Web Apps | Free tier |
| Azure Blob Storage | ~$0.02/GB/mês |
| Azure Entra ID | Free tier (até 50.000 MAU) |
| Anthropic Claude | ~$3/M tokens input, ~$15/M output |
| Qdrant Cloud | Free tier (1GB) |
| AssemblyAI | ~$0.37/hora de áudio |

Custo dominante: Anthropic API. Contexto longo com chunks grandes é o maior driver de custo — dimensionar `top_k` e tamanho de chunk com dados reais.

---

## Como rodar localmente

```bash
# 1. Copiar e preencher variáveis
cp .env.example .env
# editar .env com suas chaves

# 2. Subir backend com hot-reload
docker compose up backend

# 3. Frontend (sem Docker)
cd frontend && npm install && npm start
# → http://localhost:4200

# 4. Infra (Terraform)
az login
docker compose run --rm terraform-fmt
docker compose run --rm terraform-validate
docker compose run --rm terraform init
docker compose run --rm terraform-plan
```
