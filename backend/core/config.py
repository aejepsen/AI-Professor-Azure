from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    qdrant_url: str
    qdrant_api_key: str
    azure_tenant_id: str
    azure_client_id: str
    ragas_test_token: str
    assemblyai_api_key: str

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
