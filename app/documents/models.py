"""SQLAlchemy models for documents and document chunks."""

import uuid

from sqlalchemy import Column, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import relationship

from app.auth.models import Base


class Document(Base):
    """A medical document belonging to a tenant, with role-based access control."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    title = Column(String(500), nullable=True)
    doc_type = Column(String(100), nullable=True)
    sensitivity_tier = Column(Integer, nullable=True)
    authorized_roles = Column(ARRAY(Text), nullable=True)
    owner_patient_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    source_filename = Column(String(500), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    tenant = relationship("Tenant", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])
    owner_patient = relationship("User", foreign_keys=[owner_patient_id])


class DocumentChunk(Base):
    """A chunk of a document with its embedding vector for similarity search."""

    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    chunk_index = Column(Integer, nullable=True)
    chunk_text = Column(Text, nullable=False)
    # embedding column (vector(384)) is managed via raw SQL / pgvector
    authorized_roles = Column(ARRAY(Text), nullable=True)
    owner_patient_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    document = relationship("Document", back_populates="chunks")
