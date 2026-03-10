"""Shared application dependencies — singleton services loaded at startup."""

import logging
from typing import Optional

from app.authz.spicedb_client import SpiceDBClient
from app.config import settings
from app.rag.llm_client import OpenAILLMClient

logger = logging.getLogger(__name__)

# ── Singleton instances ──────────────────────────────────────────
_spicedb_client: Optional[SpiceDBClient] = None
_embedding_model = None
_llm_client: Optional[OpenAILLMClient] = None


def init_spicedb_client() -> SpiceDBClient:
    """Initialize and cache the SpiceDB client."""
    global _spicedb_client
    _spicedb_client = SpiceDBClient(
        endpoint=settings.SPICEDB_ENDPOINT,
        preshared_key=settings.SPICEDB_PRESHARED_KEY,
    )
    return _spicedb_client


def get_spicedb_client() -> SpiceDBClient:
    """Get the cached SpiceDB client instance."""
    global _spicedb_client
    if _spicedb_client is None:
        return init_spicedb_client()
    return _spicedb_client


def init_embedding_model():
    """Initialize and cache the sentence-transformers embedding model."""
    global _embedding_model
    from sentence_transformers import SentenceTransformer

    logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
    _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    logger.info(f"Embedding model loaded: {settings.EMBEDDING_MODEL}")
    return _embedding_model


def get_embedding_model():
    """Get the cached embedding model instance."""
    global _embedding_model
    if _embedding_model is None:
        return init_embedding_model()
    return _embedding_model


def init_llm_client() -> OpenAILLMClient:
    """Initialize and cache the OpenAI LLM client."""
    global _llm_client
    _llm_client = OpenAILLMClient(
        api_key=settings.OPENAI_API_KEY,
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
    )
    return _llm_client


def get_llm_client() -> OpenAILLMClient:
    """Get the cached LLM client instance."""
    global _llm_client
    if _llm_client is None:
        return init_llm_client()
    return _llm_client
