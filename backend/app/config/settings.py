from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    llm_model: str = Field(default="claude-sonnet-4-6")
    llm_max_tokens: int = Field(default=4096)
    llm_temperature: float = Field(default=0.1)

    # Langfuse
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")

    # PostgreSQL
    database_url: str = Field(
        default="postgresql+asyncpg://medguard:medguard_password@localhost:5432/medguard"
    )

    # Qdrant
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_collection_name: str = Field(default="medguard_knowledge")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_reload: bool = Field(default=True)
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://localhost:3000"])

    # Rate limiting
    rate_limit_requests: int = Field(default=10)
    rate_limit_window_seconds: int = Field(default=3600)

    # Agent
    max_research_retries: int = Field(default=2)
    agent_timeout_seconds: int = Field(default=120)

    # App
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def observability_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
