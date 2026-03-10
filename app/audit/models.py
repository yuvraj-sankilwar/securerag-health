"""SQLAlchemy model for retrieval audit logs."""

import uuid

from sqlalchemy import Column, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID

from app.auth.models import Base


class RetrievalAuditLog(Base):
    """Audit log entry for each RAG query."""

    __tablename__ = "retrieval_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False)
    role_name = Column(String(100), nullable=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    query_text = Column(Text, nullable=True)
    query_vector_hash = Column(String(64), nullable=True)
    retrieved_doc_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    retrieved_chunk_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    llm_response_preview = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
