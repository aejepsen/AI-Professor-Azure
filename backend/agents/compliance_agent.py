# backend/agents/compliance_agent.py
"""
Agente de compliance: valida se a resposta gerada não vaza
conteúdo além das permissões do usuário.
"""


class ComplianceAgent:
    """Valida permissões e filtra conteúdo sensível."""

    SENSITIVITY_HIERARCHY = {
        "public": 0,
        "internal": 1,
        "confidential": 2,
        "restricted": 3,
    }

    async def validate(
        self,
        answer: str,
        chunks: list[dict],
        user_groups: list[str],
    ) -> bool:
        """
        Verifica se todos os chunks usados têm permissão para o usuário.
        Retorna True se aprovado, False se deve bloquear.
        """
        for chunk in chunks:
            if not self._user_can_access(chunk, user_groups):
                return False
        return True

    async def validate_chunks(
        self,
        chunks: list[dict],
        user_groups: list[str],
    ) -> bool:
        """Versão rápida para validar apenas os chunks antes de gerar a resposta."""
        for chunk in chunks:
            label = chunk.get("sensitivity_label", "internal")
            if label == "restricted":
                # Conteúdo restrito: verifica se usuário tem grupo específico
                allowed = chunk.get("allowed_groups", [])
                if not any(g in user_groups for g in allowed):
                    return False
        return True

    def _user_can_access(self, chunk: dict, user_groups: list[str]) -> bool:
        label = chunk.get("sensitivity_label", "internal")
        allowed = chunk.get("allowed_groups", [])

        if label == "public":
            return True
        if label == "internal":
            return True  # Todos os funcionários
        if label == "confidential":
            return len(user_groups) > 0
        if label == "restricted":
            return any(g in user_groups for g in allowed)
        return False
