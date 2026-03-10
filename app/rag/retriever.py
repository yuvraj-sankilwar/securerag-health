"""RAG retriever: pgvector similarity search with SpiceDB pre-filter and RLS enforcement."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.spicedb_client import SpiceDBClient
from app.db.session import set_rls_context
from app.rag.schemas import ChunkResult

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)


class RAGRetriever:
    """
    Retrieves relevant document chunks using a triple-layer security model:
    1. SpiceDB pre-filter (get authorized document IDs)
    2. RLS context (SET LOCAL for tenant/role/user isolation)
    3. pgvector cosine similarity search within authorized scope
    """

    def __init__(self, db_session: AsyncSession, spicedb_client: SpiceDBClient, embedding_model):
        """
        Initialize the retriever.

        Args:
            db_session: Async SQLAlchemy session
            spicedb_client: SpiceDB client for authorization pre-filter
            embedding_model: sentence-transformers model for query embedding
        """
        self.db = db_session
        self.spicedb = spicedb_client
        self.model = embedding_model

    async def retrieve(
        self,
        query: str,
        user_id: str,
        role_name: str,
        tenant_id: str,
        top_k: int = 10,
    ) -> list[ChunkResult]:
        """
        Retrieve the most relevant authorized document chunks for a query.

        Args:
            query: Natural language query
            user_id: Current user's UUID
            role_name: Current user's role
            tenant_id: Current user's tenant UUID
            top_k: Maximum number of chunks to retrieve

        Returns:
            List of ChunkResult ordered by relevance (highest score first)
        """
        # ── STEP 1: SpiceDB Pre-Filter ──────────────────────────
        authorized_doc_ids = await self.spicedb.get_authorized_doc_ids(
            user_id=user_id,
            role_name=role_name,
            tenant_id=tenant_id,
        )

        if not authorized_doc_ids:
            logger.info(f"No authorized documents found for user={user_id}, role={role_name}")
            return []

        logger.debug(f"SpiceDB pre-filter returned {len(authorized_doc_ids)} authorized documents")

        # ── STEP 2: Set RLS Context ─────────────────────────────
        async with self.db.begin():
            await set_rls_context(self.db, user_id, role_name, tenant_id)

            # ── STEP 3: Embed Query ─────────────────────────────
            loop = asyncio.get_event_loop()
            query_vector = await loop.run_in_executor(
                _executor,
                lambda: self.model.encode(query).tolist(),
            )

            query_vector_str = str(query_vector)

            # ── STEP 4: pgvector Similarity Search ──────────────
            result = await self.db.execute(
                sa_text("""
                    SELECT
                        dc.id AS chunk_id,
                        dc.document_id,
                        dc.chunk_text,
                        dc.chunk_index,
                        d.title,
                        d.doc_type,
                        1 - (dc.embedding <=> CAST(:query_vector AS vector)) AS similarity_score
                    FROM document_chunks dc
                    JOIN documents d ON d.id = dc.document_id
                    WHERE dc.document_id = ANY(CAST(:authorized_ids AS uuid[]))
                    ORDER BY dc.embedding <=> CAST(:query_vector AS vector)
                    LIMIT :top_k
                """),
                {
                    "query_vector": query_vector_str,
                    "authorized_ids": authorized_doc_ids,
                    "top_k": top_k,
                },
            )

            rows = result.fetchall()

        # ── STEP 5: Format Results ──────────────────────────────
        chunks = [
            ChunkResult(
                chunk_id=str(row.chunk_id),
                document_id=str(row.document_id),
                text=row.chunk_text,
                score=float(row.similarity_score) if row.similarity_score else 0.0,
                title=row.title,
                doc_type=row.doc_type,
            )
            for row in rows
        ]

        logger.info(f"Retrieved {len(chunks)} chunks for query (user={user_id}, role={role_name})")

        return chunks
