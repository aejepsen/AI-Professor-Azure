"""Configurações da aplicação lidas de variáveis de ambiente."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    qdrant_url: str
    qdrant_api_key: str
    azure_tenant_id: str
    azure_client_id: str
    ragas_test_token: str
    assemblyai_api_key: str
    azure_storage_account_name: str
    azure_storage_account_key: str
    azure_storage_container: str = "uploads"
    cors_origins: list[str] = [
        "https://jolly-cliff-0e7c4130f.1.azurestaticapps.net",
        "http://localhost:4200",
    ]
    environment: str = "production"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
