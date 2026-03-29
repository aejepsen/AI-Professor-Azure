# backend/api/auth.py
"""
Validação de token Microsoft Entra ID para o backend FastAPI.
Implementa OBO (On-Behalf-Of) flow para trocar token do Teams.
"""

import os
import json
from dataclasses import dataclass, field
from typing import Optional

import httpx
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from msal import ConfidentialClientApplication

TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
API_SCOPE = f"api://{CLIENT_ID}/access_as_user"

# JWKS endpoint para validar tokens Entra ID
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

security = HTTPBearer()


@dataclass
class UserContext:
    id:          str
    display_name: str
    email:       str
    groups:      list[str] = field(default_factory=list)


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> UserContext:
    """
    Dependency injection: valida o Bearer token em todo endpoint protegido.
    Extrai user_id e grupos Entra ID do token.
    """
    token = credentials.credentials

    try:
        # Busca JWKS para validar assinatura
        async with httpx.AsyncClient() as client:
            jwks_response = await client.get(JWKS_URL)
            jwks = jwks_response.json()

        # Decodifica e valida o JWT
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=[CLIENT_ID, "https://graph.microsoft.com"],
            issuer=f"https://sts.windows.net/{TENANT_ID}/",
        )

        user_id      = payload.get("oid") or payload.get("sub")
        display_name = payload.get("name", "")
        email        = payload.get("preferred_username", "")

        # Grupos Entra ID estão no claim 'groups' (se configurado no App Registration)
        groups = payload.get("groups", [])

        return UserContext(
            id=user_id,
            display_name=display_name,
            email=email,
            groups=groups,
        )

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token inválido: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Erro de autenticação: {str(e)}")


async def exchange_teams_token_obo(teams_token: str) -> dict:
    """
    OBO (On-Behalf-Of) flow:
    Troca o token SSO do Teams por um token de acesso com escopo da API.
    Também busca os grupos do usuário via Microsoft Graph.
    """
    msal_app = ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )

    # OBO exchange
    result = msal_app.acquire_token_on_behalf_of(
        user_assertion=teams_token,
        scopes=["https://graph.microsoft.com/GroupMember.Read.All"],
    )

    if "error" in result:
        raise HTTPException(
            status_code=401,
            detail=f"OBO falhou: {result.get('error_description')}",
        )

    graph_token = result["access_token"]

    # Busca grupos do usuário via Graph
    async with httpx.AsyncClient() as client:
        groups_response = await client.get(
            "https://graph.microsoft.com/v1.0/me/memberOf?$select=id,displayName",
            headers={"Authorization": f"Bearer {graph_token}"},
        )
        groups_data = groups_response.json()

    groups = [g["id"] for g in groups_data.get("value", [])]

    # Gera token de acesso para a própria API
    api_result = msal_app.acquire_token_on_behalf_of(
        user_assertion=teams_token,
        scopes=[API_SCOPE],
    )

    return {
        "access_token": api_result.get("access_token"),
        "groups":       groups,
        "expires_in":   api_result.get("expires_in", 3600),
    }
