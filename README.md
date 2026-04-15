# AI Professor

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Angular](https://img.shields.io/badge/Angular-21-DD0031?logo=angular&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-4B8BBE)
![Claude](https://img.shields.io/badge/Claude-Sonnet%204.6-D97706)
![Qdrant](https://img.shields.io/badge/Qdrant-Cloud-FF4785)
![Azure](https://img.shields.io/badge/Azure-Static%20Web%20Apps%20%2B%20Container%20Apps-0078D4?logo=microsoftazure&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-1.7-7B42BC?logo=terraform&logoColor=white)

Sistema RAG corporativo que atua como **professor virtual**: os usuários fazem upload de vídeos de aulas, o sistema transcreve automaticamente e indexa o conteúdo, permitindo consultas em linguagem natural sobre o material.

![Chat](docs/screenshot.png)

---

## Arquitetura

```
Usuário (browser)
       │
       │ MSAL login (Azure Entra ID)
       ▼
┌─────────────────────┐        PUT (XHR + SAS token)       ┌──────────────────┐
│  Angular 17         │───────────────────────────────────► │  Azure Blob      │
│  Static Web App     │                                     │  Storage         │
│  (Azure, Free tier) │◄────── SSE streaming ───────────── │  (uploads)       │
└─────────┬───────────┘                                     └────────┬─────────┘
          │ Bearer JWT                                               │ SAS read
          ▼                                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Azure Container Apps (Consumption, scale-to-zero)        │
│                                                                             │
│  FastAPI  ──►  LangGraph Agent  ──►  KnowledgeService (Qdrant hybrid)      │
│                      │                                                      │
│              AssemblyAI SDK (transcrição)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
          │                        │                        │
          ▼                        ▼                        ▼
   Qdrant Cloud           Anthropic API             AssemblyAI API
   (busca híbrida)       (Claude Sonnet 4.6)       (transcrição vídeo)
```

---

## Stack Tecnológica

### Backend
| Tecnologia | Uso |
|---|---|
| Python 3.11 + FastAPI | API REST + streaming SSE |
| LangGraph (StateGraph) | Orquestração do agente RAG |
| Claude Sonnet 4.6 | Geração de respostas |
| Qdrant Cloud | Busca vetorial híbrida (dense + sparse) |
| AssemblyAI SDK | Transcrição automática de vídeo |
| PyJWT[crypto] | Validação de JWT RS256 (Azure Entra ID) |

### Frontend
| Tecnologia | Uso |
|---|---|
| Angular 21 (standalone) | SPA com componentes standalone |
| MSAL Angular | Autenticação Microsoft (redirect flow) |
| Azure Static Web Apps | Hospedagem + roteamento |

### Infraestrutura
| Tecnologia | Uso |
|---|---|
| Terraform | IaC 100% — nenhum recurso criado manualmente |
| GitHub Actions | CI (testes + build) e CD (deploy) |
| Azure Container Apps | Backend (0.5 CPU / 2Gi, scale-to-zero) |
| Azure Blob Storage | Upload direto do frontend via SAS token |
| GitHub Container Registry | Imagens Docker |

### AI/ML
| Tecnologia | Uso |
|---|---|
| Claude Sonnet 4.6 | LLM principal |
| multilingual-e5-large | Embeddings densos |
| BM25 (Qdrant sparse) | Busca esparsa híbrida |
| RAGAS | Avaliação de qualidade RAG |

---

## Features Principais

- **Upload de vídeo** — frontend faz PUT direto ao Azure Blob via SAS token (backend nunca recebe o arquivo)
- **Transcrição automática** — AssemblyAI processa o vídeo e retorna transcrição completa
- **Indexação RAG** — transcrição chunked, embeddings gerados e indexados no Qdrant
- **Chat com streaming** — respostas em tempo real via SSE, com citação das fontes
- **Autenticação Microsoft** — MSAL redirect flow, JWT validado no backend
- **Cold start visível** — barra "Iniciando servidor..." no frontend enquanto o container sobe (scale-to-zero)
- **Observabilidade** — logs estruturados, métricas RAGAS, health check `/health`
- **Cobertura de testes** — 95%+ (pytest unit + integration + docker smoke tests)

---

## Como Rodar Localmente

### Pré-requisitos
- Python 3.11
- Node.js 22
- Docker (opcional)
- Conta Qdrant Cloud (ou instância local)
- Chave API Anthropic e AssemblyAI

### Backend

```bash
# Execute a partir da raiz do projeto (AI-Professor/)
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Copie e preencha as variáveis de ambiente
cp .env.example .env

uvicorn backend.api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm start
# Acesse http://localhost:4200
```

---

## Produção

| Recurso | URL |
|---|---|
| **Frontend** | https://red-moss-0108f120f.7.azurestaticapps.net |
| **Backend** | https://ai-professor-backend.bravebush-60555594.eastus.azurecontainerapps.io |
| **Health** | https://ai-professor-backend.bravebush-60555594.eastus.azurecontainerapps.io/health |

> ⚠️ O Container App environment ID (`bravebush-60555594`) muda a cada `terraform destroy + apply`. Sempre verificar com `az containerapp show --query "properties.configuration.ingress.fqdn"` e atualizar `frontend/src/app/services/api.service.ts` e `backend/core/config.py`.

---

## Deploy

### Pre-deploy obrigatório (antes de qualquer push)

```bash
# 1. Testes
python -m pytest backend/tests/unit/ -q --tb=short

# 2. Dependencias em venv limpo
python -m venv /tmp/test-venv && source /tmp/test-venv/bin/activate
pip install -r backend/requirements-prod.txt -q
python -c "import fastapi, uvicorn, multipart, sentence_transformers, torch; print(torch.__version__)"
deactivate && rm -rf /tmp/test-venv

# 3. Verificar URLs — nunca confiar no hardcoded
az containerapp show --name ai-professor-backend --resource-group ai-professor-prod-rg \
  --query "properties.configuration.ingress.fqdn" -o tsv
```

Consulte a skill `/hm-azure-ml-deploy` para o checklist completo de armadilhas conhecidas.

### Infraestrutura (primeira vez ou após terraform destroy)

```bash
cd infra/terraform
terraform init
terraform plan -out=tfplan -var-file="prod.tfvars"   # revisar antes de apply
terraform apply tfplan
```

Após o apply:
```bash
terraform output                                          # anotar todas as URLs
az ad app show --id <api-client-id> --query identifierUris  # deve estar preenchido
# Se identifierUris vazio:
az ad app update --id <api-client-id> --identifier-uris "api://<api-client-id>"

# Atualizar GitHub Secret com novo token do SWA:
terraform output -raw static_web_app_api_key

# Atualizar URLs hardcoded no frontend e config:
# frontend/src/app/services/api.service.ts → BACKEND_URL
# frontend/src/app/app.config.ts → clientId (terraform state show azuread_application.frontend | grep client_id)
# backend/core/config.py → cors_origins
```

### Aplicação

Push para `main` dispara CD automaticamente. Para forçar deploy manual:

```bash
git push origin main
# ou workflow_dispatch via GitHub Actions UI (deploya backend + frontend)
```

O GitHub Actions:
1. Detecta quais partes mudaram (`backend/**` ou `frontend/**`)
2. Testes Python → Build Docker → Push GHCR → Deploy Container App
3. Deploy do Angular no Azure Static Web Apps (paralelo ou sequencial)

---

## Variáveis de Ambiente

| Variável | Descrição |
|---|---|
| `ANTHROPIC_API_KEY` | Chave da API Anthropic (Claude) |
| `QDRANT_URL` | URL do cluster Qdrant Cloud |
| `QDRANT_API_KEY` | Chave de acesso ao Qdrant |
| `AZURE_TENANT_ID` | ID do tenant Azure Entra ID |
| `AZURE_CLIENT_ID` | Client ID do App Registration da API |
| `ASSEMBLYAI_API_KEY` | Chave da API AssemblyAI |
| `AZURE_STORAGE_ACCOUNT_NAME` | Nome da conta de armazenamento Azure |
| `AZURE_STORAGE_ACCOUNT_KEY` | Chave de acesso ao Azure Blob Storage |
| `AZURE_STORAGE_CONTAINER` | Nome do container de uploads |
| `RAGAS_TEST_TOKEN` | Token para avaliação RAGAS |

---

## Estrutura de Diretórios

```
AI-Professor/
├── backend/
│   ├── api/
│   │   ├── main.py          # FastAPI app + middlewares
│   │   ├── routes/          # chat, ingest, health
│   │   ├── auth.py          # Validação JWT RS256 (Azure)
│   │   └── schemas.py       # Pydantic schemas
│   ├── agents/              # LangGraph StateGraph (RAG)
│   ├── services/            # KnowledgeService, ChatService, BlobService
│   ├── core/                # Config (pydantic-settings)
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── docker/
│   └── requirements.txt
├── frontend/
│   ├── src/app/
│   │   ├── pages/           # chat, ingest
│   │   ├── services/        # api, auth, chat-state, ingest-state
│   │   └── nav/             # componente de navegação
│   └── package.json
├── infra/
│   └── terraform/           # 100% IaC
├── .github/
│   └── workflows/
│       ├── ci.yml           # Testes + build + terraform plan
│       └── cd.yml           # Deploy para Azure
└── README.md
```

---

## Licença

MIT License — veja [LICENSE](LICENSE) para detalhes.
