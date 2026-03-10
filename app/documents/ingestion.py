"""Document ingestion pipeline: text extraction, chunking, embedding, and storage."""

import asyncio
import io
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.permissions import get_roles_for_doc_type, is_role_authorized_for_doc_type
from app.authz.spicedb_client import SpiceDBClient
from app.config import settings

logger = logging.getLogger(__name__)

# Thread pool for running synchronous embedding operations
_executor = ThreadPoolExecutor(max_workers=4)


class DocumentIngestionService:
    """
    Handles the full document ingestion pipeline:
    1. Validate permissions
    2. Extract text from file
    3. Chunk text using recursive character splitting
    4. Generate embeddings via sentence-transformers
    5. Store document and chunks in the database
    6. Write SpiceDB relationships
    """

    def __init__(self, db_session: AsyncSession, spicedb_client: SpiceDBClient, embedding_model):
        """
        Initialize the ingestion service.

        Args:
            db_session: Async SQLAlchemy session
            spicedb_client: SpiceDB client for writing relationships
            embedding_model: sentence-transformers model instance
        """
        self.db = db_session
        self.spicedb = spicedb_client
        self.model = embedding_model

    async def ingest_document(
        self,
        file_bytes: bytes,
        filename: str,
        doc_type: str,
        tenant_id: str,
        created_by_user: str,
        role_name: str,
        sensitivity_tier: int = 1,
        owner_patient_id: Optional[str] = None,
    ) -> dict:
        """
        Ingest a document: extract text, chunk, embed, store, and set permissions.

        Args:
            file_bytes: Raw file content
            filename: Original filename
            doc_type: Document type (e.g., "EHR", "RADIOLOGY_REPORT")
            tenant_id: Tenant UUID
            created_by_user: User UUID of the uploader
            role_name: Role name of the uploader
            sensitivity_tier: Sensitivity level (1=public, 4=restricted)
            owner_patient_id: Optional patient owner UUID

        Returns:
            Dict with document_id and chunk_count

        Raises:
            PermissionError: If the user's role cannot upload this doc_type
        """
        # Step 1: Validate permissions
        if not is_role_authorized_for_doc_type(role_name, doc_type):
            raise PermissionError(f"Role '{role_name}' is not authorized to upload documents of type '{doc_type}'")

        # Step 2: Extract text
        extracted_text = await self._extract_text(file_bytes, filename)
        if not extracted_text.strip():
            raise ValueError("No text content could be extracted from the file")

        # Step 3: Chunk text
        chunks = self._chunk_text(extracted_text)
        logger.info(f"Split document into {len(chunks)} chunks")

        # Step 4: Generate embeddings (run in thread pool since sentence-transformers is sync)
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            _executor,
            lambda: self.model.encode(chunks, show_progress_bar=False).tolist(),
        )

        # Step 5: Determine authorized roles
        authorized_roles = get_roles_for_doc_type(doc_type)

        # Step 6: Insert Document record
        doc_id = str(uuid.uuid4())
        title = filename.rsplit(".", 1)[0] if "." in filename else filename

        await self.db.execute(
            sa_text("""
                INSERT INTO documents (id, tenant_id, title, doc_type, sensitivity_tier,
                    authorized_roles, owner_patient_id, source_filename, created_by)
                VALUES (:id, :tenant_id, :title, :doc_type, :sensitivity_tier,
                    :authorized_roles, :owner_patient_id, :source_filename, :created_by)
            """),
            {
                "id": doc_id,
                "tenant_id": tenant_id,
                "title": title,
                "doc_type": doc_type.upper(),
                "sensitivity_tier": sensitivity_tier,
                "authorized_roles": authorized_roles,
                "owner_patient_id": owner_patient_id,
                "source_filename": filename,
                "created_by": created_by_user,
            },
        )

        # Step 7: Bulk insert DocumentChunk records with embeddings
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = str(uuid.uuid4())
            embedding_str = str(embedding)

            await self.db.execute(
                sa_text("""
                    INSERT INTO document_chunks (id, document_id, tenant_id, chunk_index,
                        chunk_text, embedding, authorized_roles, owner_patient_id)
                    VALUES (:id, :document_id, :tenant_id, :chunk_index,
                        :chunk_text, CAST(:embedding AS vector), :authorized_roles, :owner_patient_id)
                """),
                {
                    "id": chunk_id,
                    "document_id": doc_id,
                    "tenant_id": tenant_id,
                    "chunk_index": idx,
                    "chunk_text": chunk_text,
                    "embedding": embedding_str,
                    "authorized_roles": authorized_roles,
                    "owner_patient_id": owner_patient_id,
                },
            )

        await self.db.flush()

        # Step 8: Write SpiceDB relationships
        relationships = []

        # document#tenant → tenant
        relationships.append(
            {
                "resource_type": "document",
                "resource_id": doc_id,
                "relation": "tenant",
                "subject_type": "tenant",
                "subject_id": tenant_id,
            }
        )

        # document#authorized_role → role (for each authorized role)
        for role in authorized_roles:
            relationships.append(
                {
                    "resource_type": "document",
                    "resource_id": doc_id,
                    "relation": "authorized_role",
                    "subject_type": "role",
                    "subject_id": role.lower(),
                }
            )

        # document#owner → user (for patient-owned documents)
        if owner_patient_id:
            relationships.append(
                {
                    "resource_type": "document",
                    "resource_id": doc_id,
                    "relation": "owner",
                    "subject_type": "user",
                    "subject_id": owner_patient_id,
                }
            )

        await self.spicedb.write_relationships(relationships)

        logger.info(
            f"Ingested document '{title}' (id={doc_id}) with {len(chunks)} chunks, type={doc_type}, tenant={tenant_id}"
        )

        return {"document_id": doc_id, "chunk_count": len(chunks)}

    async def _extract_text(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract text from a file. Supports .txt and .pdf formats.

        Args:
            file_bytes: Raw file content
            filename: Original filename (used to determine format)

        Returns:
            Extracted text content
        """
        lower_filename = filename.lower()

        if lower_filename.endswith(".pdf"):
            return await self._extract_pdf_text(file_bytes)
        elif lower_filename.endswith(".txt"):
            return file_bytes.decode("utf-8", errors="replace")
        else:
            # Fall back to treating as plain text
            return file_bytes.decode("utf-8", errors="replace")

    async def _extract_pdf_text(self, file_bytes: bytes) -> str:
        """Extract text from a PDF file using pypdf."""
        from pypdf import PdfReader

        loop = asyncio.get_event_loop()

        def _read_pdf():
            reader = PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n\n".join(text_parts)

        return await loop.run_in_executor(_executor, _read_pdf)

    def _chunk_text(self, text: str) -> list[str]:
        """
        Split text into chunks using recursive character splitting.

        Splits on paragraph boundaries, then sentence boundaries, then word boundaries.
        Uses CHUNK_SIZE and CHUNK_OVERLAP from settings.

        Args:
            text: Full document text

        Returns:
            List of text chunks
        """
        chunk_size = settings.CHUNK_SIZE
        chunk_overlap = settings.CHUNK_OVERLAP
        separators = ["\n\n", "\n", ". ", " "]

        return self._recursive_split(text, separators, chunk_size, chunk_overlap)

    def _recursive_split(self, text: str, separators: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
        """
        Recursively split text using a hierarchy of separators.

        Args:
            text: Text to split
            separators: Ordered list of separators to try
            chunk_size: Maximum chunk size in characters
            chunk_overlap: Number of overlapping characters between chunks

        Returns:
            List of text chunks
        """
        if not text:
            return []

        # If text fits in one chunk, return it
        if len(text) <= chunk_size:
            return [text.strip()] if text.strip() else []

        # Find the best separator to use
        separator = separators[-1]  # default to last separator
        for sep in separators:
            if sep in text:
                separator = sep
                break

        # Split text by separator
        parts = text.split(separator)

        # Merge parts into chunks respecting chunk_size
        chunks = []
        current_chunk = ""

        for part in parts:
            test_chunk = current_chunk + separator + part if current_chunk else part

            if len(test_chunk) <= chunk_size:
                current_chunk = test_chunk
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                # Start new chunk with overlap
                if chunk_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-chunk_overlap:]
                    current_chunk = overlap_text + separator + part
                else:
                    current_chunk = part

        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks
