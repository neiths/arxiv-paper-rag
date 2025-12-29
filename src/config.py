from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DefaultSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        frozen=True,
        env_nested_delimiter="__",
    )


class Settings(DefaultSettings):
    """Application settings."""

    app_version: str = "1.0.0"
    debug: bool = True
    environment: str = "development"
    service_name: str = "rag_api"

    # PostgresSQL configuration
    postgres_database_url: str = "postgresql+psycopg2://rag_user:rag_password@localhost:5432/rag_db"
    postgres_echo_sql: bool = False
    postgres_pool_size: int = 20
    postgres_max_overflow: int = 0

    # OpenSearch configuration
    opensearch_host: str = "http://localhost:9200"

    # Ollama configuration
    ollama_host: str = "http://localhost:11434"
    ollama_models: Union[str, List[str]] = Field(default=["mistral:7b", "llama3.2:1b"])
    ollama_default_model: str = "llama3.2:1b"
    ollama_timeout: int = 300   # 5 minutes

    @field_validator("ollama_models", mode="before")
    @classmethod
    def parse_ollama_models(cls, v):
        """Parse comma-separated string into list of models."""
        if isinstance(v, str):
            return [model.strip() for model in v.split(",") if model.strip()]
        return v


class ArxivSettings(DefaultSettings):
    """Arxiv API client settings."""

    base_url = "https://export.arxiv.org/api/query"
    namespaces: dict = Field(
        default={
            "atom": "http://www.w3.org/2005/Atom",
            "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
    )
    pdf_cache_dir: str = "./data/arxiv_pdfs"
    rate_limit_delay: float = 3.0  # seconds
    timeout_seconds: int = 30
    max_results: int = 100
    search_category: str = "cs.AI"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()