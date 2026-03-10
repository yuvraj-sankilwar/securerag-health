"""Pydantic schemas for document endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    """Response body for document upload."""

    document_id: UUID
    chunk_count: int
    message: str = "Document ingested successfully"


class DocumentListItem(BaseModel):
    """Single document in list response."""

    id: UUID
    title: Optional[str] = None
    doc_type: Optional[str] = None
    sensitivity_tier: Optional[int] = None
    source_filename: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Response body for document listing."""

    documents: list[DocumentListItem]
    total_count: int
