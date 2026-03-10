"""SQLAlchemy models for authentication: User, Role, Tenant."""

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Tenant(Base):
    """Hospital department / organizational unit."""

    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    name = Column(String(255), unique=True, nullable=False)
    department_code = Column(String(50), unique=True, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    users = relationship("User", back_populates="tenant")
    documents = relationship("app.documents.models.Document", back_populates="tenant")


class Role(Base):
    """User role in the hospital (PHYSICIAN, NURSE, etc.)."""

    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    users = relationship("User", back_populates="role")


class User(Base):
    """Hospital staff member or patient."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    is_active = Column(Boolean, server_default=text("true"), default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    role = relationship("Role", back_populates="users")
    tenant = relationship("Tenant", back_populates="users")
