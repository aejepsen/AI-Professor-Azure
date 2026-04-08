# AI Professor

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Angular](https://img.shields.io/badge/Angular-17-DD0031?logo=angular&logoColor=white)
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
| python-jose | Validação de JWT (Azure Entra ID) |

### Frontend
| Tecnologia | Uso |
|---|---|
| Angular 17 (standalone) | SPA com componentes standalone |
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
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copie e preencha as variáveis de ambiente
cp .env.example .env

uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm start
# Acesse http://localhost:4200
```

---

## Deploy

### Infraestrutura (primeira vez ou após terraform destroy)

```bash
cd infra/terraform
terraform init
terraform apply -var-file="prod.tfvars"
```

Após o apply, atualizar o GitHub Secret `AZURE_STATIC_WEB_APPS_API_TOKEN` com o novo token:

```bash
terraform output -raw static_web_app_api_key
```

### Aplicação

Push para a branch `main` dispara o workflow de CD automaticamente:

```
git push origin main
```

O GitHub Actions:
1. Faz build da imagem Docker e push para GHCR
2. Atualiza o Container App com a nova imagem
3. Deploy do frontend no Azure Static Web Apps

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
│   ├── app/
│   │   ├── main.py          # FastAPI app + rotas
│   │   ├── agent/           # LangGraph StateGraph
│   │   ├── services/        # KnowledgeService, StorageService
│   │   └── auth/            # Validação JWT
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── docker/
│   └── requirements.txt
├── frontend/
│   ├── src/app/
│   │   ├── components/      # Chat, Upload, etc.
│   │   └── services/        # API, Auth
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
