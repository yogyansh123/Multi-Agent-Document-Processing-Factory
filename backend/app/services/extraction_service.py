"""
services/extraction_service.py
==============================
Service orchestrating the LangGraph Information Extraction Agent.

Responsibilities:
- Verify document exists, OCR text is available, and classification has completed.
- Append a ProcessingHistory record for stage=EXTRACTION.
- Execute the LangGraph extraction workflow.
- Update Document status to EXTRACTED and persist validated structured JSON.
- Handle failure states cleanly without leaking stack traces.
- Support re-extraction (updates fields, appends fresh history record).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.extraction.graph import create_extraction_graph
from app.agents.extraction.prompts import EXTRACTION_PROMPT_VERSION
from app.agents.extraction.state import ExtractionState
from app.core.enums import DocumentStatus, ProcessingStage, StageStatus
from app.core.logging import get_logger
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.services.document import DocumentNotFoundError
from app.services.llm.base import LLMProvider

logger = get_logger(__name__)


class ExtractionServiceError(Exception):
    """Base exception for extraction service operations."""


class OcrNotCompletedForExtractionError(ExtractionServiceError):
    """Raised when extraction is attempted before OCR has finished."""

    def __init__(self, document_id: uuid.UUID, current_status: str) -> None:
        self.document_id = document_id
        self.current_status = current_status
        super().__init__(
            f"Document {document_id!s} has status '{current_status}'. "
            "OCR must be completed before information extraction can run."
        )


class ClassificationNotCompletedForExtractionError(ExtractionServiceError):
    """Raised when extraction is attempted before classification has finished."""

    def __init__(self, document_id: uuid.UUID, current_status: str) -> None:
        self.document_id = document_id
        self.current_status = current_status
        super().__init__(
            f"Document {document_id!s} has not been classified yet (status: '{current_status}'). "
            "Document classification must precede information extraction."
        )


class DocumentNotExtractedError(ExtractionServiceError):
    """Raised when extraction results are requested for an unextracted document."""

    def __init__(self, document_id: uuid.UUID, current_status: str) -> None:
        self.document_id = document_id
        self.current_status = current_status
        super().__init__(
            f"Document {document_id!s} has not been extracted yet (current status: '{current_status}')."
        )


class ExtractionError(ExtractionServiceError):
    """Raised when the extraction agent encounters an unrecoverable error."""


class ExtractionService:
    """
    Coordinates document information extraction execution and persistence.
    """

    def __init__(self, db: AsyncSession, llm: LLMProvider) -> None:
        self._db = db
        self._llm = llm

    async def extract_document(self, document_id: uuid.UUID) -> Document:
        """
        Execute the Information Extraction Agent for the given document.

        1. Load document by ID.
        2. Validate OCR and Classification have completed.
        3. Append ProcessingHistory record (stage=EXTRACTION, status=IN_PROGRESS).
        4. Execute LangGraph extraction workflow.
        5. Persist extracted structured data and transition status to EXTRACTED.
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

        # Validate OCR completed
        if not document.ocr_text or not document.ocr_text.strip():
            raise OcrNotCompletedForExtractionError(document_id, document.status)

        # Validate Classification completed
        if not document.document_type:
            raise ClassificationNotCompletedForExtractionError(document_id, document.status)

        start_time = datetime.now(timezone.utc)

        # Audit record
        history = ProcessingHistory(
            id=uuid.uuid4(),
            document_id=document.id,
            stage=ProcessingStage.EXTRACTION.value,
            status=StageStatus.IN_PROGRESS.value,
            message=f"Starting information extraction for {document.document_type} with LangGraph agent...",
            started_at=start_time,
            completed_at=None,
        )
        self._db.add(history)
        await self._db.flush()

        logger.info(
            "extraction.started",
            document_id=str(document.id),
            document_type=document.document_type,
            provider=self._llm.provider_name,
        )

        try:
            # Build and execute the LangGraph workflow
            graph = create_extraction_graph(llm_provider=self._llm, db=self._db)

            initial_state: ExtractionState = {
                "document_id": str(document.id),
                "document_text": document.ocr_text,
                "document_type": document.document_type,
            }

            final_state: ExtractionState = await graph.ainvoke(initial_state)

            if final_state.get("error"):
                raise ExtractionError(final_state["error"])

            now = datetime.now(timezone.utc)
            document.extracted_data = final_state.get("extracted_data")
            document.extraction_version = (
                final_state.get("extraction_version") or EXTRACTION_PROMPT_VERSION
            )
            document.extracted_at = now
            document.status = DocumentStatus.EXTRACTED.value
            document.error_message = None

            history.status = StageStatus.COMPLETED.value
            history.completed_at = now
            history.message = (
                f"Information extraction completed for {document.document_type} "
                f"(version {document.extraction_version})."
            )

            await self._db.flush()
            await self._db.refresh(document)

            logger.info(
                "extraction.completed",
                document_id=str(document.id),
                document_type=document.document_type,
                version=document.extraction_version,
            )
            return document

        except Exception as exc:
            finish_time = datetime.now(timezone.utc)
            document.status = DocumentStatus.FAILED.value
            document.error_message = f"Extraction failed: {str(exc)}"

            history.status = StageStatus.FAILED.value
            history.completed_at = finish_time
            history.error_details = str(exc)
            history.message = f"Extraction failed: {str(exc)}"

            await self._db.flush()
            await self._db.refresh(document)

            logger.error(
                "extraction.failed",
                document_id=str(document.id),
                error=str(exc),
            )
            if isinstance(exc, ExtractionServiceError):
                raise
            raise ExtractionError(f"Extraction failed: {str(exc)}") from exc

    async def get_extraction(self, document_id: uuid.UUID) -> Document:
        """
        Retrieve structured extraction data for a document.

        Raises:
        - DocumentNotFoundError if document does not exist.
        - DocumentNotExtractedError if document has not yet completed extraction.
        """
        stmt = select(Document).where(Document.id == document_id)
        result = await self._db.execute(stmt)
        document = result.scalar_one_or_none()

        if document is None:
            raise DocumentNotFoundError(document_id)

        if document.status != DocumentStatus.EXTRACTED.value and not document.extracted_data:
            raise DocumentNotExtractedError(document_id, document.status)

        return document
