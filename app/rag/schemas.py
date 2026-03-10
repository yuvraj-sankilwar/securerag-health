"""Pydantic schemas for RAG endpoints."""

from typing import Optional

from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    """Request body for RAG query."""

    query: str = Field(..., min_length=3, max_length=1000, description="Natural language query")
    top_k: int = Field(default=10, ge=1, le=20, description="Number of chunks to retrieve")


class SourceReference(BaseModel):
    """A source document reference in the RAG response (no raw text or internal IDs)."""

    title: Optional[str] = None
    doc_type: Optional[str] = None
    similarity_score: float


class RAGQueryResponse(BaseModel):
    """Response body for RAG query."""

    query: str
    answer: str
    sources: list[SourceReference]
    retrieved_chunk_count: int
    latency_ms: int
    role_used: str
    tenant_id: str


class ChunkResult(BaseModel):
    """Internal representation of a retrieved chunk (not exposed in API)."""

    chunk_id: str
    document_id: str
    text: str
    score: float
    title: Optional[str] = None
    doc_type: Optional[str] = None
