# backend/agents/search_agent.py
"""
Agente de Busca — Retrieval híbrido no Azure AI Search.
Filtro de permissão aplicado DENTRO do índice (antes de qualquer dado sair).
"""

import os
import json
import httpx
from openai import AsyncAzureOpenAI


SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY      = os.getenv("AZURE_SEARCH_KEY")
SEARCH_INDEX    = os.getenv("AZURE_SEARCH_INDEX", "ai-professor-index")
OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
OPENAI_KEY      = os.getenv("AZURE_OPENAI_KEY")
EMBEDDING_MODEL = "text-embedding-3-large"


class SearchAgent:
    """
    Executa busca híbrida (BM25 + vetorial) com:
    - Filtro de permissão por grupos Entra ID
    - Filtro por nível de sensibilidade
    - Reranking semântico
    - Boost por tipo de conteúdo baseado na intenção
    """

    async def search(
        self,
        query: str,
        user_groups: list[str],
        intent: str = "general",
        top: int = 8,
    ) -> list[dict]:

        # 1. Gera embedding da pergunta
        embedding = await self._embed(query)

        # 2. Filtro de permissão — OData filter do Azure AI Search
        #    O filtro é aplicado DENTRO do índice antes de retornar resultados
        permission_filter = self._build_permission_filter(user_groups)

        # 3. Busca híbrida com reranking semântico
        results = await self._hybrid_search(
            query=query,
            embedding=embedding,
            permission_filter=permission_filter,
            intent=intent,
            top=top,
        )

        return results

    async def _embed(self, text: str) -> list[float]:
        client = AsyncAzureOpenAI(
            azure_endpoint=OPENAI_ENDPOINT,
            api_key=OPENAI_KEY,
            api_version="2024-02-01",
        )
        response = await client.embeddings.create(
            input=text,
            model=EMBEDDING_MODEL,
        )
        return response.data[0].embedding

    def _build_permission_filter(self, user_groups: list[str]) -> str:
        """
        Constrói filtro OData que garante que só chunks acessíveis ao usuário
        sejam retornados — filtro executado no Azure AI Search, não no Python.
        """
        if not user_groups:
            # Usuário sem grupos — apenas conteúdo público
            return "sensitivity_label eq 'public'"

        # Conteúdo público OU qualquer grupo que o usuário pertença
        group_conditions = " or ".join(
            [f"permission_groups/any(g: g eq '{gid}')" for gid in user_groups]
        )
        return f"(sensitivity_label eq 'public' or sensitivity_label eq 'internal' or ({group_conditions}))"

    async def _hybrid_search(
        self,
        query: str,
        embedding: list[float],
        permission_filter: str,
        intent: str,
        top: int,
    ) -> list[dict]:
        """
        Busca híbrida: BM25 (texto) + vetorial (semântico) + reranking.
        Documentação: https://learn.microsoft.com/azure/search/hybrid-search-overview
        """
        # Boost por tipo de conteúdo baseado na intenção
        boost_filter = None
        if intent == "video":
            boost_filter = "source_type eq 'video'"
        elif intent in ("document", "policy"):
            boost_filter = f"source_type eq '{intent}'"

        search_body = {
            "search":       query,
            "filter":       permission_filter,
            "top":          top,
            "queryType":    "semantic",
            "semanticConfiguration": "ai-professor-semantic",
            "queryLanguage": "pt-BR",
            "captions":     "extractive",
            "answers":      "extractive|count-3",
            "vectorQueries": [
                {
                    "vector":   embedding,
                    "fields":   "embedding",
                    "kind":     "vector",
                    "k":        top * 2,   # over-fetch para reranking
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/search",
                headers={
                    "Content-Type":  "application/json",
                    "api-key":       SEARCH_KEY,
                    "api-version":   "2024-05-01-preview",
                },
                json=search_body,
            )
            response.raise_for_status()
            data = response.json()

        chunks = []
        for item in data.get("value", []):
            chunks.append({
                "id":                    item["id"],
                "content":               item["content"],
                "source_type":           item["source_type"],
                "source_name":           item["source_name"],
                "source_url":            item["source_url"],
                "sensitivity_label":     item["sensitivity_label"],
                "timestamp_start":       item.get("timestamp_start"),
                "timestamp_end":         item.get("timestamp_end"),
                "timestamp_start_seconds": item.get("timestamp_start_seconds"),
                "timestamp_end_seconds":   item.get("timestamp_end_seconds"),
                "page":                  item.get("page_number"),
                "topics":                item.get("topics", []),
                "quality_score":         item.get("quality_score", 0.8),
                "@search.reranker_score": item.get("@search.rerankerScore", 0.0),
                "@search.highlights":    item.get("@search.captions", []),
            })

        return chunks
