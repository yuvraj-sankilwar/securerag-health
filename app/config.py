"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """SecureRAG-Health application settings loaded from environment variables."""

    # ── PostgreSQL ───────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://rag_app_user:apppass@localhost:5432/securerag"
    DATABASE_SYNC_URL: str = "postgresql+psycopg2://rag_app_user:apppass@localhost:5432/securerag"
    DB_APP_USER: str = "rag_app_user"
    DB_APP_PASSWORD: str = "apppass"

    # ── SpiceDB ──────────────────────────────────────────────────
    SPICEDB_ENDPOINT: str = "localhost:50051"
    SPICEDB_PRESHARED_KEY: str = "dev-secret-key"

    # ── Redis ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Anthropic LLM ────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = "sk-ant-placeholder"
    LLM_MODEL: str = "claude-sonnet-4-20250514"
    LLM_MAX_TOKENS: int = 1500

    # ── JWT ──────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-this-in-production-use-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    # ── Embeddings & RAG ─────────────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    TOP_K_CHUNKS: int = 10

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
