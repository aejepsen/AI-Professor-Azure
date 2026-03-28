# backend/services/prompt_service.py
"""
Serviço de prompts: carrega e cacheia o system prompt do AI Professor.
"""

import os
import functools
from pathlib import Path

PROMPT_DIR = Path(__file__).parent.parent / "prompts"
DEFAULT_PROMPT = """Você é o AI Professor, assistente de conhecimento corporativo da empresa.
Responda em português do Brasil de forma clara, precisa e profissional.
Baseie suas respostas exclusivamente no contexto fornecido.
Se não encontrar a informação no contexto, diga honestamente que não sabe.
Cite as fontes ao final de cada resposta usando o formato [1], [2], etc."""


@functools.lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """Carrega o system prompt do arquivo, com cache em memória."""
    prompt_file = PROMPT_DIR / "system_prompt_v2.txt"
    try:
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return DEFAULT_PROMPT


def reload_prompt() -> str:
    """Força recarga do prompt (limpa cache)."""
    load_system_prompt.cache_clear()
    return load_system_prompt()
