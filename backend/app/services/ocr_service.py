"""
services/ocr_service.py
=======================
Service orchestrating OCR execution for documents.

Responsibilities:
- Retrieve document by ID (raise DocumentNotFoundError if missing).
- Resolve physical storage file path safely.
- Atomically update Document status to PROCESSING.
- Append ProcessingHistory record for stage=OCR.
- Delegate extraction to the injected OCRProvider.
- On success:
    - Update Document status to OCR_COMPLETED.
    - Persist extracted text, provider, page_count, processing_time_ms, completed_at, metadata.
    - Mark ProcessingHistory as COMPLETED.
- On failure:
    - Update Document status to FAILED.
    - Record sanitized error message on Document and ProcessingHistory.
    - Mark ProcessingHistory as FAILED.
    - Re-raise OCRError.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.enums import DocumentStatus, ProcessingStage, StageStatus
from app.core.logging import get_logger
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.services.document import DocumentNotFoundError
from app.services.ocr.base import OCRError, OCRProvider
from app.services.storage.base import StorageProvider

logger = get_logger(__name__)


class OcrNotCompletedError(Exception):
    """Raised when text is requested for a document that has not completed OCR."""

    def __init__(self, document_id: uuid.UUID, status: str) -> None:
        self.document_id = document_id
        self.status = status
        super().__init__(
            f"Document {document_id!s} has status '{status}'. "
            "OCR must be completed before extracting full text."
        )


class OcrService:
    """
    Coordinates document OCR extraction and database persistence.
    """

    def __init__(
        self,
        db: AsyncSession,
        storage: StorageProvider,
        ocr: OCRProvider,
    ) -> None:
        self._db = db
        self._storage = storage
        self._ocr = ocr

    async def run_ocr(self, document_id: uuid.UUID) -> Document:
        """
        Run OCR on the specified document.

        1. Fetch document.
        2. Resolve file path and verify file exists.
        3. Transition document status to PROCESSING.
        4. Create ProcessingHistory record for stage=OCR.
        5. Invoke OCR provider.
        6. On success: update document fields + history -> OCR_COMPLETED.
        7. On failure: update document fields + history -> FAILED, re-raise.
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

        # Resolve path
        if hasattr(self._storage, "root"):
            storage_root = getattr(self._storage, "root")
        else:
            storage_root = Path(settings.STORAGE_PATH).resolve()
        abs_file_path = (storage_root / document.file_path).resolve()

        if not abs_file_path.is_file():
            logger.error(
                "ocr.file_not_found",
                document_id=str(document_id),
                file_path=str(abs_file_path),
            )
            now = datetime.now(timezone.utc)
            document.status = DocumentStatus.FAILED.value
            document.error_message = f"File not found on storage: {document.original_filename}"
            failed_history = ProcessingHistory(
                id=uuid.uuid4(),
                document_id=document.id,
                stage=ProcessingStage.OCR.value,
                status=StageStatus.FAILED.value,
                message=f"Storage file missing: {document.file_path}",
                error_details="Physical file not found on disk",
                started_at=now,
                completed_at=now,
            )
            self._db.add(failed_history)
            await self._db.flush()
            raise OCRError(
                f"File not found on storage for document {document_id!s}",
                provider=self._ocr.provider_name,
            )

        start_time = datetime.now(timezone.utc)
        document.status = DocumentStatus.PROCESSING.value
        document.error_message = None

        history = ProcessingHistory(
            id=uuid.uuid4(),
            document_id=document.id,
            stage=ProcessingStage.OCR.value,
            status=StageStatus.IN_PROGRESS.value,
            message=f"Starting OCR extraction with provider '{self._ocr.provider_name}'",
            started_at=start_time,
            completed_at=None,
        )
        self._db.add(history)
        await self._db.flush()

        logger.info(
            "ocr.started",
            document_id=str(document.id),
            provider=self._ocr.provider_name,
            file_type=document.file_type,
        )

        try:
            ocr_result = await self._ocr.extract_text(
                str(abs_file_path),
                document.file_type,
            )
            finish_time = datetime.now(timezone.utc)

            document.ocr_text = ocr_result.text
            document.ocr_provider = ocr_result.provider
            document.ocr_page_count = ocr_result.page_count
            document.ocr_processing_time_ms = ocr_result.processing_time_ms
            document.ocr_completed_at = finish_time
            document.ocr_metadata = ocr_result.metadata
            document.status = DocumentStatus.OCR_COMPLETED.value
            document.error_message = None

            history.status = StageStatus.COMPLETED.value
            history.completed_at = finish_time
            history.message = (
                f"OCR completed successfully using {ocr_result.provider} "
                f"({ocr_result.page_count} page(s) in {ocr_result.processing_time_ms}ms)."
            )

            await self._db.flush()
            await self._db.refresh(document)

            logger.info(
                "ocr.completed",
                document_id=str(document.id),
                provider=ocr_result.provider,
                page_count=ocr_result.page_count,
                processing_time_ms=ocr_result.processing_time_ms,
            )
            return document

        except Exception as exc:
            finish_time = datetime.now(timezone.utc)
            document.status = DocumentStatus.FAILED.value
            document.error_message = f"OCR failed: {str(exc)}"

            history.status = StageStatus.FAILED.value
            history.completed_at = finish_time
            history.error_details = str(exc)
            history.message = f"OCR failed: {str(exc)}"

            await self._db.flush()
            await self._db.refresh(document)

            logger.error(
                "ocr.failed",
                document_id=str(document.id),
                provider=self._ocr.provider_name,
                error=str(exc),
            )
            if isinstance(exc, OCRError):
                raise
            raise OCRError(
                f"OCR extraction failed: {str(exc)}",
                provider=self._ocr.provider_name,
                cause=exc,
            ) from exc

    async def get_document_text(self, document_id: uuid.UUID) -> Document:
        """
        Retrieve a document and ensure OCR has completed.

        Raises:
        - DocumentNotFoundError if document does not exist.
        - OcrNotCompletedError if document.status != OCR_COMPLETED.
        """
        stmt = select(Document).where(Document.id == document_id)
        result = await self._db.execute(stmt)
        document = result.scalar_one_or_none()

        if document is None:
            raise DocumentNotFoundError(document_id)

        if document.status != DocumentStatus.OCR_COMPLETED.value:
            raise OcrNotCompletedError(document_id, document.status)

        return document
