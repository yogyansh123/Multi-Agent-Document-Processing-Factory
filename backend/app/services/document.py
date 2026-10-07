"""
services/document.py
=====================
Document service — all business logic for document management.

This module is the single authoritative source for:
- Validating uploads (type, size)
- Persisting documents to the database
- Creating ProcessingHistory records
- Querying documents with pagination
- Deleting documents (physical file + database records)

Architecture rules enforced here:
- No FastAPI types (Request, UploadFile, etc.) — pure Python.
- No SQLAlchemy models returned directly — return dicts used to build schemas.
- Structured logging on every significant operation.
- Raise domain-specific exceptions; let the router handle HTTP status codes.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.enums import DocumentStatus, ProcessingStage, StageStatus
from app.core.logging import get_logger
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.services.storage.base import StorageProvider

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class DocumentServiceError(Exception):
    """Base class for all document service errors."""


class UnsupportedFileTypeError(DocumentServiceError):
    """Raised when the uploaded file type is not in the allow-list."""

    def __init__(self, file_type: str, allowed: list[str]) -> None:
        self.file_type = file_type
        self.allowed = allowed
        super().__init__(
            f"File type {file_type!r} is not supported. "
            f"Allowed types: {allowed}"
        )


class FileTooLargeError(DocumentServiceError):
    """Raised when the uploaded file exceeds the configured size limit."""

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"File size {size_bytes:,} bytes exceeds the maximum "
            f"allowed size of {max_bytes:,} bytes "
            f"({max_bytes // (1024 * 1024)} MB)."
        )


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a requested document does not exist."""

    def __init__(self, document_id: uuid.UUID) -> None:
        self.document_id = document_id
        super().__init__(f"Document {document_id!s} not found.")


class StorageOperationError(DocumentServiceError):
    """Raised when a storage backend operation fails."""


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------


def _calc_total_pages(total: int, page_size: int) -> int:
    """Return the total number of pages given a total item count and page size."""
    if page_size <= 0:
        return 0
    return math.ceil(total / page_size) if total > 0 else 0


# ---------------------------------------------------------------------------
# Document Service
# ---------------------------------------------------------------------------


class DocumentService:
    """
    Service class encapsulating all document management business logic.

    Parameters
    ----------
    db:
        An async SQLAlchemy session (injected by FastAPI dependency).
    storage:
        A StorageProvider instance (injected by FastAPI dependency).
    """

    # Maximum and default pagination limits
    MAX_PAGE_SIZE: int = 100
    DEFAULT_PAGE_SIZE: int = 20

    def __init__(self, db: AsyncSession, storage: StorageProvider) -> None:
        self._db = db
        self._storage = storage

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    async def upload_document(
        self,
        file_bytes: bytes,
        original_filename: str,
        content_type: str,
    ) -> Document:
        """
        Validate, store, and persist a new document.

        Steps:
        1. Validate file type against ALLOWED_UPLOAD_TYPES.
        2. Validate file size against MAX_UPLOAD_SIZE_BYTES.
        3. Save file bytes to the storage backend.
        4. Insert a Document row with status=UPLOADED.
        5. Append a ProcessingHistory record for the UPLOAD stage.
        6. Return the persisted Document (for schema serialisation).

        Raises
        ------
        UnsupportedFileTypeError: file type not in allow-list.
        FileTooLargeError: file exceeds MAX_UPLOAD_SIZE_MB.
        StorageOperationError: storage backend could not save the file.
        """
        file_type = self._extract_extension(original_filename, content_type)
        self._validate_file_type(file_type)
        self._validate_file_size(len(file_bytes))

        # Save to storage
        try:
            stored = await self._storage.save(
                file_bytes=file_bytes,
                original_filename=original_filename,
                mime_type=content_type,
            )
        except Exception as exc:
            logger.error(
                "storage.save.failed",
                original_filename=original_filename,
                error=str(exc),
            )
            raise StorageOperationError(
                f"Failed to store file {original_filename!r}: {exc}"
            ) from exc

        # Persist document record
        doc_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        document = Document(
            id=doc_id,
            original_filename=original_filename,
            stored_filename=stored.stored_filename,
            file_path=stored.file_path,
            file_type=file_type,
            mime_type=stored.mime_type,
            file_size=stored.file_size,
            document_type=None,
            status=DocumentStatus.UPLOADED.value,
        )
        self._db.add(document)

        # Create initial processing history record
        history = ProcessingHistory(
            id=uuid.uuid4(),
            document_id=doc_id,
            stage=ProcessingStage.UPLOAD.value,
            status=StageStatus.COMPLETED.value,
            message=f"File '{original_filename}' uploaded successfully.",
            started_at=now,
            completed_at=now,
        )
        self._db.add(history)

        await self._db.flush()  # Assign DB defaults without committing
        await self._db.refresh(document)

        logger.info(
            "document.uploaded",
            document_id=str(doc_id),
            original_filename=original_filename,
            file_type=file_type,
            size_bytes=stored.file_size,
        )

        return document

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------

    async def get_document(self, document_id: uuid.UUID) -> Document:
        """
        Fetch a single document by ID including its processing history.

        Raises
        ------
        DocumentNotFoundError: no document with the given ID exists.
        """
        stmt = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.processing_history))
        )
        result = await self._db.execute(stmt)
        document = result.scalar_one_or_none()

        if document is None:
            raise DocumentNotFoundError(document_id)

        return document

    async def list_documents(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        status: str | None = None,
        document_type: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """
        Return a paginated list of documents ordered by upload time (newest first),
        with optional status, document_type, and filename search filtering.
        """
        page = max(1, page)
        page_size = max(1, min(page_size, self.MAX_PAGE_SIZE))
        offset = (page - 1) * page_size

        base_query = select(Document)
        count_query = select(func.count()).select_from(Document)

        if status and status.strip().upper() != "ALL":
            base_query = base_query.where(Document.status == status.strip().upper())
            count_query = count_query.where(Document.status == status.strip().upper())

        if document_type and document_type.strip().upper() != "ALL":
            base_query = base_query.where(Document.document_type == document_type.strip().upper())
            count_query = count_query.where(Document.document_type == document_type.strip().upper())

        if search and search.strip():
            term = f"%{search.strip()}%"
            base_query = base_query.where(Document.original_filename.ilike(term))
            count_query = count_query.where(Document.original_filename.ilike(term))

        total: int = (await self._db.execute(count_query)).scalar_one()

        items_stmt = (
            base_query.order_by(Document.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self._db.execute(items_stmt)
        documents = list(items_result.scalars().all())

        return {
            "items": documents,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": _calc_total_pages(total, page_size),
        }

    async def get_summary_stats(self) -> dict[str, Any]:
        """Compute aggregate dashboard metrics across all documents."""
        status_stmt = select(Document.status, func.count(Document.id)).group_by(Document.status)
        status_res = await self._db.execute(status_stmt)
        status_counts = dict(status_res.all())

        total = sum(status_counts.values())

        avg_stmt = select(func.avg(Document.overall_confidence)).where(Document.overall_confidence.isnot(None))
        avg_res = await self._db.execute(avg_stmt)
        avg_conf = avg_res.scalar()
        avg_conf_rounded = round(float(avg_conf), 4) if avg_conf is not None else None

        rag_stmt = select(func.count(Document.id)).where(Document.rag_indexed.is_(True))
        rag_res = await self._db.execute(rag_stmt)
        rag_count = rag_res.scalar() or 0

        return {
            "total_documents": total,
            "processing": status_counts.get("PROCESSING", 0),
            "approved": status_counts.get("APPROVED", 0),
            "review_required": status_counts.get("REVIEW_REQUIRED", 0),
            "rejected": status_counts.get("REJECTED", 0),
            "failed": status_counts.get("FAILED", 0),
            "average_confidence": avg_conf_rounded,
            "rag_indexed_count": rag_count,
        }


    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_document(self, document_id: uuid.UUID) -> None:
        """
        Delete a document — removes the stored file and the database record.

        ProcessingHistory rows are deleted automatically via the CASCADE
        relationship defined on Document.

        Raises
        ------
        DocumentNotFoundError: no document with the given ID exists.
        StorageOperationError: storage deletion failed.
        """
        document = await self.get_document(document_id)

        # Attempt to delete the physical file first
        try:
            await self._storage.delete(document.file_path)
        except FileNotFoundError:
            # File already gone — log a warning but continue cleanup
            logger.warning(
                "storage.delete.file_not_found",
                document_id=str(document_id),
                file_path=document.file_path,
            )
        except Exception as exc:
            logger.error(
                "storage.delete.failed",
                document_id=str(document_id),
                file_path=document.file_path,
                error=str(exc),
            )
            raise StorageOperationError(
                f"Failed to delete file for document {document_id!s}: {exc}"
            ) from exc

        # Delete the database record (cascade removes history rows)
        await self._db.delete(document)
        await self._db.flush()

        logger.info(
            "document.deleted",
            document_id=str(document_id),
            original_filename=document.original_filename,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_extension(filename: str, content_type: str) -> str:
        """
        Derive the file extension from the filename.

        Uses the filename suffix (lowercased, without the dot).
        Falls back to content type parsing if no suffix is present.
        """
        from pathlib import Path
        suffix = Path(filename).suffix.lstrip(".").lower()
        if suffix:
            return suffix
        # Minimal content-type fallback
        ct_map = {
            "application/pdf": "pdf",
            "image/png": "png",
            "image/jpeg": "jpg",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        }
        return ct_map.get(content_type.lower(), "bin")

    @staticmethod
    def _validate_file_type(file_type: str) -> None:
        """Raise UnsupportedFileTypeError if file_type not in ALLOWED_UPLOAD_TYPES."""
        allowed = settings.ALLOWED_UPLOAD_TYPES
        if file_type.lower() not in [t.lower() for t in allowed]:
            raise UnsupportedFileTypeError(file_type, allowed)

    @staticmethod
    def _validate_file_size(size_bytes: int) -> None:
        """Raise FileTooLargeError if size_bytes exceeds MAX_UPLOAD_SIZE_BYTES."""
        max_bytes = settings.MAX_UPLOAD_SIZE_BYTES
        if size_bytes > max_bytes:
            raise FileTooLargeError(size_bytes, max_bytes)
