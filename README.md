# AI Professor — Agente Inteligente Corporativo v3.0

Angular 17 + FastAPI + LangGraph + Claude claude-opus-4-5 — Microsoft Teams Tab App.

## Estrutura.

```
ai-professor/
├── src/                    # Angular — Teams Tab App
│   ├── app/
│   │   ├── app.component.ts        # Root + splash de inicialização
│   │   ├── app.config.ts           # Bootstrap: MSAL + NgRx + Router
│   │   ├── app.routes.ts           # Lazy routes com TeamsAuthGuard
│   │   ├── core/auth/              # SSO silencioso + interceptor Bearer
│   │   ├── core/services/          # TeamsService + ChatService (SSE)
│   │   ├── core/store/             # NgRx: chat + upload state
│   │   ├── shell/                  # Layout: sidebar + nav + user profile
│   │   ├── chat/                   # Chat com streaming token-a-token
│   │   ├── history/                # Histórico com busca e exportação
│   │   ├── knowledge/              # Browser da base de conhecimento
│   │   ├── upload/                 # Drag-and-drop + progress em tempo real
│   │   ├── dashboard/              # Métricas RAGAS + gaps + KPIs
│   │   └── shared/source-panel/    # Fontes com timestamps clicáveis
│   ├── styles.scss                 # Fluent UI tokens (Light/Dark/Contrast)
│   └── index.html                  # HTML com CSP para Teams
├── teams/manifest.json             # Teams App Manifest v1.17
├── frontend/tests/e2e/             # Playwright E2E
├── backend/
│   ├── api/main.py                 # FastAPI: REST + SSE streaming
│   ├── api/auth.py                 # Entra ID validation + OBO flow
│   ├── agents/graph.py             # LangGraph multi-agent
│   ├── agents/search_agent.py      # Azure AI Search hybrid retrieval
│   ├── agents/video_agent.py       # Timestamps de vídeo
│   ├── agents/compliance_agent.py  # Filtro de permissão
│   ├── agents/memory_agent.py      # Histórico de sessão
│   ├── agents/evaluator_agent.py   # RAGAS em background
│   ├── services/                   # Conversation, Knowledge, Dashboard, Ingest
│   ├── prompts/system_prompt_v2.txt
│   └── tests/test_agents.py        # Pytest unitários
├── pipeline/
│   ├── transcribe.py               # Azure Speech + timestamps
│   ├── enrich.py                   # Claude: correção + segmentação
│   ├── evaluate_quality.py         # WER, CER, coerência
│   ├── chunk.py                    # Chunking semântico
│   ├── embed.py                    # text-embedding-3-large
│   └── index.py                    # Azure AI Search + schema
├── evaluation/ragas_eval.py        # Quality gate CI/CD
├── infrastructure/terraform/main.tf # IaC completo
├── .github/workflows/deploy.yml    # CI/CD: test → build → deploy → E2E → RAGAS
├── angular.json
├── playwright.config.ts
└── package.json
```

## Setup Frontend

```bash
npm install
cp src/environments/environment.example.ts src/environments/environment.ts
# Edite: clientId, tenantId, apiUrl, apiScope
ng serve
```

## Setup Backend

```bash
cd backend && pip install -r requirements.txt

export ANTHROPIC_API_KEY="..."
export AZURE_TENANT_ID="..."
export AZURE_CLIENT_ID="..."
export AZURE_CLIENT_SECRET="..."
export AZURE_SEARCH_ENDPOINT="https://ai-professor.search.windows.net"
export AZURE_SEARCH_KEY="..."
export AZURE_OPENAI_ENDPOINT="..."
export AZURE_OPENAI_KEY="..."
export AZURE_STORAGE_CONNECTION_STRING="..."
export AZURE_SPEECH_KEY="..."

uvicorn api.main:app --reload --port 8000
```

## Testes

```bash
pytest backend/tests/ -v --cov=backend   # Unit tests
npx playwright test                       # E2E (requer ng serve)
python evaluation/ragas_eval.py           # Quality gate RAGAS
```

## Deploy Teams

1. Substitua variáveis em `teams/manifest.json`
2. `cd teams && zip -r ../ai-professor-app.zip .`
3. Upload no Teams Admin Center → Manage apps

## Infraestrutura

```bash
cd infrastructure/terraform
terraform init && terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars
```

## KPIs

| Métrica | Meta |
|---|---|
| RAGAS Faithfulness | >= 0.85 |
| Tempo resposta P95 | < 4s |
| CSAT | >= 4.2/5.0 |
| Taxa de resolução | >= 80% |
| FCP Angular Tab | < 1.5s |
