"""Application settings loaded from environment / .env via Pydantic Settings.

Single source of configuration truth. Nothing in the codebase reads os.environ directly.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # Application
    environment: Literal["development", "staging", "production", "test"] = "development"
    app_name: str = "enterprise-ai-platform"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Security
    secret_key: str = Field(min_length=16)
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    # Initial admin
    admin_email: str = "admin@example.com"
    admin_password: str = "ChangeMe123!"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "eap"
    postgres_password: str = "eap-secret"
    postgres_db: str = "eap"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_prefix: str = "eap"

    # Provider API keys (optional — presence enables the provider)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    mistral_api_key: str = ""
    deepseek_api_key: str = ""
    openrouter_api_key: str = ""
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "eu-west-1"
    vertex_project_id: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Model defaults
    default_llm_provider: str = "anthropic"
    default_llm_model: str = "claude-sonnet-5"
    fallback_llm_provider: str = "openai"
    fallback_llm_model: str = "gpt-4o"
    default_embedding_provider: str = "openai"
    default_embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # RAG defaults
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    rag_top_k: int = 8
    rag_similarity_threshold: float = 0.35
    rag_rerank_enabled: bool = True

    # Rate limiting
    rate_limit_requests_per_minute: int = 120
    llm_rate_limit_tokens_per_minute: int = 200_000

    # Observability
    otel_exporter_otlp_endpoint: str = ""
    prometheus_metrics_enabled: bool = True

    # MLflow / Celery
    mlflow_tracking_uri: str = "http://localhost:5000"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Uploads
    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 50

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor used everywhere via dependency injection."""
    return Settings()  # type: ignore[call-arg]
