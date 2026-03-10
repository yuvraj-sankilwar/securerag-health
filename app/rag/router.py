"""RAG query router: POST /rag/query."""

import asyncio
import hashlib
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.jwt_handler import get_current_user
from app.auth.schemas import TokenPayload
from app.db.session import get_db
from app.dependencies import get_embedding_model, get_llm_client, get_spicedb_client
from app.rag.prompt_builder import build_prompt
from app.rag.retriever import RAGRetriever
from app.rag.schemas import RAGQueryRequest, RAGQueryResponse, SourceReference

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(
    request: RAGQueryRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Query the RAG system.

    1. Retrieves authorized document chunks via triple-layer security
    2. Builds a constrained prompt with retrieved context
    3. Generates a response using OpenAI
    4. Writes an async audit log
    5. Returns the answer with source references (no raw chunk text)
    """
    start_time = time.time()

    # Get dependencies
    spicedb_client = get_spicedb_client()
    embedding_model = get_embedding_model()
    llm_client = get_llm_client()

    # Fail-closed: if SpiceDB is unavailable, return 503
    if not spicedb_client.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authorization service is unavailable. Please try again later.",
        )

    # Step 1: Retrieve relevant chunks
    retriever = RAGRetriever(db, spicedb_client, embedding_model)

    try:
        chunks = await retriever.retrieve(
            query=request.query,
            user_id=current_user.user_id,
            role_name=current_user.role_name,
            tenant_id=current_user.tenant_id,
            top_k=request.top_k,
        )
    except Exception as e:
        logger.error(f"Retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document retrieval failed",
        )

    # Step 2: Handle no results
    if not chunks:
        latency_ms = int((time.time() - start_time) * 1000)
        return RAGQueryResponse(
            query=request.query,
            answer="No authorized documents found. You may not have access to documents related to this query, "
            "or no relevant documents exist in the system.",
            sources=[],
            retrieved_chunk_count=0,
            latency_ms=latency_ms,
            role_used=current_user.role_name,
            tenant_id=current_user.tenant_id,
        )

    # Step 3: Build prompt
    messages = build_prompt(
        query=request.query,
        chunks=chunks,
        role_name=current_user.role_name,
        user_name=current_user.email,
    )

    # Step 4: Generate LLM response
    try:
        answer = await llm_client.generate(messages)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM service is unavailable. Please try again later.",
        )

    latency_ms = int((time.time() - start_time) * 1000)

    # Step 5: Build source references (NO raw chunk text, NO internal IDs)
    sources = [
        SourceReference(
            title=chunk.title,
            doc_type=chunk.doc_type,
            similarity_score=round(chunk.score, 4),
        )
        for chunk in chunks
    ]

    # Step 6: Write audit log (fire-and-forget)
    query_vector_hash = hashlib.sha256(request.query.encode()).hexdigest()
    asyncio.create_task(
        write_audit_log(
            user_id=current_user.user_id,
            role_name=current_user.role_name,
            tenant_id=current_user.tenant_id,
            query_text=request.query,
            query_vector_hash=query_vector_hash,
            retrieved_doc_ids=[chunk.document_id for chunk in chunks],
            retrieved_chunk_ids=[chunk.chunk_id for chunk in chunks],
            llm_response_preview=answer[:500] if answer else "",
            latency_ms=latency_ms,
        )
    )

    # Step 7: Return response
    return RAGQueryResponse(
        query=request.query,
        answer=answer,
        sources=sources,
        retrieved_chunk_count=len(chunks),
        latency_ms=latency_ms,
        role_used=current_user.role_name,
        tenant_id=current_user.tenant_id,
    )
