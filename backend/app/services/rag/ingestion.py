"""
services/rag/ingestion.py
=========================
RAG ingestion service for segmenting, embedding, and indexing processed documents.

Responsibilities:
- Verify document eligibility (only APPROVED documents, reject REJECTED/incomplete)
- Deterministic text chunking
- Dense vector embedding generation
- Transactional and idempotent chunk replacement in PostgreSQL (pgvector)
- Update Document RAG indexing metadata
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DocumentStatus
from app.core.logging import get_logger
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.rag.chunking import chunk_document_text
from app.services.rag.embeddings import EmbeddingProvider, get_embedding_provider

logger = get_logger("app.services.rag.ingestion")


class RagIngestionError(Exception):
    """Base exception for RAG ingestion failures."""


class DocumentNotFoundError(RagIngestionError):
    """Raised when document does not exist."""


class OcrNotCompletedError(RagIngestionError):
    """Raised when document has no extracted OCR text."""


class DocumentNotEligibleForIndexingError(RagIngestionError):
    """Raised when document is rejected or not yet approved."""


@dataclass
class DocumentIndexResult:
    """Result returned by index_document."""
    document_id: uuid.UUID
    chunks_created: int
    status: str
    indexed_at: datetime
    embedding_model: str



class RagIngestionService:
    """
    Manages the segmentation, embedding, and vector database persistence
    for document intelligence search.
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider or get_embedding_provider()

    async def _get_document(self, document_id: uuid.UUID) -> Document:
        stmt = select(Document).where(Document.id == document_id)
        result = await self.db.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        return doc

    async def index_document(
        self,
        document_id: uuid.UUID,
        allow_force: bool = False,
    ) -> tuple[int, list[DocumentChunk]]:
        """
        Segment, embed, and index an approved document.

        Rules:
        - Document must exist
        - OCR text must be present
        - Document status must be APPROVED (unless allow_force=True for testing)
        - REJECTED documents cannot be indexed
        - Idempotent: replaces any previously existing chunks for this document
        """
        document = await self._get_document(document_id)

        # 1. Eligibility verification
        if document.status == DocumentStatus.REJECTED.value:
            raise DocumentNotEligibleForIndexingError(
                f"Document {document_id} is REJECTED and cannot be indexed into RAG corpus."
            )

        if not allow_force and document.status != DocumentStatus.APPROVED.value:
            raise DocumentNotEligibleForIndexingError(
                f"Document {document_id} has status {document.status}. "
                f"Only APPROVED documents can be indexed into RAG corpus."
            )

        # 2. Text verification
        if not document.ocr_text or not document.ocr_text.strip():
            raise OcrNotCompletedError(
                f"Document {document_id} cannot be indexed: OCR text is missing."
            )

        logger.info(
            "rag_indexing_started",
            document_id=str(document_id),
            doc_type=document.document_type,
            filename=document.original_filename,
        )

        # 3. Chunking
        meta = {
            "document_id": str(document.id),
            "filename": document.original_filename,
            "document_type": document.document_type or "OTHER",
        }
        text_chunks = chunk_document_text(document.ocr_text, document_metadata=meta)

        if not text_chunks:
            logger.warning("rag_indexing_empty_chunks", document_id=str(document_id))
            return 0, []

        # 4. Generate embeddings
        chunk_texts = [c.content for c in text_chunks]
        embeddings = await self.embedding_provider.embed_documents(chunk_texts)

        now = datetime.now(timezone.utc)
        model_name = getattr(self.embedding_provider, "model", "fake-embedding")

        try:
            # 5. Idempotent replacement: delete existing chunks for this document
            del_stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
            await self.db.execute(del_stmt)

            # 6. Insert new DocumentChunk records
            chunk_records: list[DocumentChunk] = []
            for tc, emb in zip(text_chunks, embeddings):
                record = DocumentChunk(
                    document_id=document.id,
                    chunk_index=tc.chunk_index,
                    content=tc.content,
                    page_number=tc.page_number,
                    token_count=tc.token_count,
                    embedding=emb,
                    chunk_metadata={
                        **tc.metadata,
                        "embedding_model": model_name,
                        "indexed_at": now.isoformat(),
                    },
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(record)
                chunk_records.append(record)

            # 7. Update document RAG metadata
            document.rag_indexed = True
            document.rag_indexed_at = now
            document.rag_chunk_count = len(chunk_records)
            document.rag_embedding_model = model_name

            await self.db.commit()
            for rec in chunk_records:
                await self.db.refresh(rec)
            await self.db.refresh(document)

            logger.info(
                "rag_indexing_completed",
                document_id=str(document_id),
                chunks_created=len(chunk_records),
                embedding_model=model_name,
            )

            return DocumentIndexResult(
                document_id=document.id,
                chunks_created=len(chunk_records),
                status="INDEXED",
                indexed_at=now,
                embedding_model=model_name,
            )

        except Exception as exc:
            await self.db.rollback()
            logger.error("rag_indexing_failed", document_id=str(document_id), error=str(exc))
            raise RagIngestionError(f"RAG indexing transaction failed: {exc}") from exc

    async def remove_document_index(self, document_id: uuid.UUID) -> int:
        """
        Remove a document from the RAG vector index (e.g. if rejected or deleted).
        """
        document = await self._get_document(document_id)
        del_stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        res = await self.db.execute(del_stmt)
        count = res.rowcount or 0

        document.rag_indexed = False
        document.rag_indexed_at = None
        document.rag_chunk_count = 0
        document.rag_embedding_model = None

        await self.db.commit()
        await self.db.refresh(document)
        return count

    async def get_index_status(self, document_id: uuid.UUID) -> dict[str, Any]:
        """Query RAG indexing status for a document."""
        document = await self._get_document(document_id)
        return {
            "document_id": str(document.id),
            "indexed": bool(document.rag_indexed),
            "chunk_count": document.rag_chunk_count or 0,
            "indexed_at": document.rag_indexed_at,
            "embedding_model": document.rag_embedding_model,
        }
