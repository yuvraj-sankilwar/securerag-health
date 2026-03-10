"""Async audit log writer — fire-and-forget audit logging."""

import logging

from sqlalchemy import text as sa_text

from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def write_audit_log(
    user_id: str,
    role_name: str,
    tenant_id: str,
    query_text: str,
    query_vector_hash: str,
    retrieved_doc_ids: list[str],
    retrieved_chunk_ids: list[str],
    llm_response_preview: str,
    latency_ms: int,
) -> None:
    """
    Write a retrieval audit log entry.

    This is designed to be called via asyncio.create_task() for fire-and-forget
    behavior — it should not block the API response.

    Args:
        user_id: The querying user's UUID
        role_name: The user's role
        tenant_id: The user's tenant UUID
        query_text: The original query text
        query_vector_hash: SHA-256 hash of the query embedding
        retrieved_doc_ids: List of document UUIDs that were retrieved
        retrieved_chunk_ids: List of chunk UUIDs that were retrieved
        llm_response_preview: First 500 chars of the LLM response
        latency_ms: Total query latency in milliseconds
    """
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    sa_text("""
                        INSERT INTO retrieval_audit_logs
                            (user_id, role_name, tenant_id, query_text, query_vector_hash,
                             retrieved_doc_ids, retrieved_chunk_ids, llm_response_preview, latency_ms)
                        VALUES
                            (:user_id, :role_name, :tenant_id, :query_text, :query_vector_hash,
                             :retrieved_doc_ids, :retrieved_chunk_ids, :llm_response_preview, :latency_ms)
                    """),
                    {
                        "user_id": user_id,
                        "role_name": role_name,
                        "tenant_id": tenant_id,
                        "query_text": query_text,
                        "query_vector_hash": query_vector_hash,
                        "retrieved_doc_ids": retrieved_doc_ids,
                        "retrieved_chunk_ids": retrieved_chunk_ids,
                        "llm_response_preview": llm_response_preview[:500] if llm_response_preview else "",
                        "latency_ms": latency_ms,
                    },
                )
        logger.debug(f"Audit log written for user={user_id}, latency={latency_ms}ms")
    except Exception as e:
        # Audit log failures should not crash the application
        logger.error(f"Failed to write audit log: {e}", exc_info=True)
