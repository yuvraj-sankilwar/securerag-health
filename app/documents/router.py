"""Document management router: /documents/upload, /documents/list."""

import logging
from typing import Optional

from app.dependencies import get_embedding_model, get_spicedb_client
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_handler import get_current_user
from app.auth.schemas import TokenPayload
from app.authz.permissions import is_role_authorized_for_doc_type
from app.db.session import get_db, set_rls_context
from app.documents.ingestion import DocumentIngestionService
from app.documents.schemas import DocumentListItem, DocumentListResponse, DocumentUploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    sensitivity_tier: int = Form(1),
    owner_patient_id: Optional[str] = Form(None),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and ingest a document.

    - Validates that the user's role can upload this document type
    - Extracts text from the uploaded file (supports .txt and .pdf)
    - Chunks and embeds the text
    - Stores the document and chunks in the database
    - Sets up SpiceDB relationships for access control
    """
    # Validate role authorization for this doc_type
    if not is_role_authorized_for_doc_type(current_user.role_name, doc_type):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_user.role_name}' is not authorized to upload documents of type '{doc_type}'",
        )

    # Read file content
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # Get dependencies
    spicedb_client = get_spicedb_client()
    embedding_model = get_embedding_model()

    # Create ingestion service and ingest
    service = DocumentIngestionService(db, spicedb_client, embedding_model)

    try:
        result = await service.ingest_document(
            file_bytes=file_bytes,
            filename=file.filename or "unnamed_document",
            doc_type=doc_type.upper(),
            tenant_id=current_user.tenant_id,
            created_by_user=current_user.user_id,
            role_name=current_user.role_name,
            sensitivity_tier=sensitivity_tier,
            owner_patient_id=owner_patient_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document ingestion failed",
        )

    return DocumentUploadResponse(
        document_id=result["document_id"],
        chunk_count=result["chunk_count"],
    )


@router.get("/list", response_model=DocumentListResponse)
async def list_documents(
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List documents visible to the current user's role and tenant.

    RLS policies automatically filter results based on the user's tenant,
    role, and patient ownership.
    """
    try:
        async with db.begin():
            await set_rls_context(
                db,
                user_id=current_user.user_id,
                role_name=current_user.role_name,
                tenant_id=current_user.tenant_id,
            )

            result = await db.execute(
                sa_text("""
                    SELECT id, title, doc_type, sensitivity_tier, source_filename, created_at
                    FROM documents
                    ORDER BY created_at DESC
                """)
            )
            rows = result.fetchall()

        documents = [
            DocumentListItem(
                id=row.id,
                title=row.title,
                doc_type=row.doc_type,
                sensitivity_tier=row.sensitivity_tier,
                source_filename=row.source_filename,
                created_at=row.created_at,
            )
            for row in rows
        ]

        return DocumentListResponse(
            documents=documents,
            total_count=len(documents),
        )

    except Exception as e:
        logger.error(f"Document listing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents",
        )
