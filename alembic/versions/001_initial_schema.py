"""Initial schema for SecureRAG-Health.

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enable pgvector extension ────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── Tenants ──────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("department_code", sa.String(50), unique=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    # ── Roles ────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
    )

    # ── Users ────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    # ── Documents ────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("doc_type", sa.String(100), nullable=True),
        sa.Column("sensitivity_tier", sa.Integer, nullable=True),
        sa.Column("authorized_roles", ARRAY(sa.Text), nullable=True),
        sa.Column("owner_patient_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source_filename", sa.String(500), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    # ── Document Chunks ──────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=True),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("embedding", sa.Column.__class__, nullable=True),  # handled via raw SQL below
        sa.Column("authorized_roles", ARRAY(sa.Text), nullable=True),
        sa.Column("owner_patient_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    # Drop the placeholder embedding column and add the proper vector column
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(384)")

    # ── Retrieval Audit Logs ─────────────────────────────────────
    op.create_table(
        "retrieval_audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role_name", sa.String(100), nullable=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("query_text", sa.Text, nullable=True),
        sa.Column("query_vector_hash", sa.String(64), nullable=True),
        sa.Column("retrieved_doc_ids", ARRAY(UUID(as_uuid=True)), nullable=True),
        sa.Column("retrieved_chunk_ids", ARRAY(UUID(as_uuid=True)), nullable=True),
        sa.Column("llm_response_preview", sa.Text, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    # ── Indexes ──────────────────────────────────────────────────
    op.execute("CREATE INDEX idx_chunk_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX idx_chunk_tenant_roles ON document_chunks (tenant_id, authorized_roles)")
    op.execute("CREATE INDEX idx_doc_tenant_roles ON documents (tenant_id, authorized_roles)")

    # ── Row Level Security ───────────────────────────────────────
    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE documents FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY rls_chunk_isolation ON document_chunks
        USING (
            tenant_id::text = current_setting('app.tenant_id', true)
            AND current_setting('app.role_name', true) = ANY(authorized_roles)
            AND (
                owner_patient_id IS NULL
                OR owner_patient_id::text = current_setting('app.user_id', true)
            )
        )
    """)

    op.execute("""
        CREATE POLICY rls_doc_isolation ON documents
        USING (
            tenant_id::text = current_setting('app.tenant_id', true)
            AND current_setting('app.role_name', true) = ANY(authorized_roles)
            AND (
                owner_patient_id IS NULL
                OR owner_patient_id::text = current_setting('app.user_id', true)
            )
        )
    """)

    # ── Application Role ─────────────────────────────────────────
    # Create application-level db user (non-superuser) for RLS enforcement
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'rag_app_user') THEN
                CREATE ROLE rag_app_user LOGIN PASSWORD 'apppass';
            END IF;
        END
        $$;
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO rag_app_user")
    op.execute("GRANT USAGE ON SCHEMA public TO rag_app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_chunk_isolation ON document_chunks")
    op.execute("DROP POLICY IF EXISTS rls_doc_isolation ON documents")
    op.drop_table("retrieval_audit_logs")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("tenants")
    op.execute("DROP EXTENSION IF EXISTS vector")
