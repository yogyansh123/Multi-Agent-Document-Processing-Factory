"""
services/classification_service.py
==================================
Service orchestrating the LangGraph Document Classification Agent.

Responsibilities:
- Verify document exists and OCR text is available.
- Append a ProcessingHistory record for stage=CLASSIFICATION.
- Execute the LangGraph classification workflow.
- Update Document status to CLASSIFIED and persist classification details.
- Handle failure states cleanly without leaking stack traces.
- Support reclassification (updates fields, appends fresh history record).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.classification.graph import create_classification_graph
from app.agents.classification.state import ClassificationState
from app.core.enums import DocumentStatus, ProcessingStage, StageStatus
from app.core.logging import get_logger
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.services.document import DocumentNotFoundError
from app.services.llm.base import LLMProvider

logger = get_logger(__name__)


class ClassificationServiceError(Exception):
    """Base exception for classification service operations."""


class OcrNotCompletedForClassificationError(ClassificationServiceError):
    """Raised when classification is attempted before OCR is completed."""

    def __init__(self, document_id: uuid.UUID, current_status: str) -> None:
        self.document_id = document_id
        self.current_status = current_status
        super().__init__(
            f"Document {document_id!s} has status '{current_status}'. "
            "OCR must be completed before classification can run."
        )


class DocumentNotClassifiedError(ClassificationServiceError):
    """Raised when classification results are requested for an unclassified document."""

    def __init__(self, document_id: uuid.UUID, current_status: str) -> None:
        self.document_id = document_id
        self.current_status = current_status
        super().__init__(
            f"Document {document_id!s} has not been classified yet (current status: '{current_status}')."
        )


class ClassificationError(ClassificationServiceError):
    """Raised when the classification agent fails to classify the document."""


class ClassificationService:
    """
    Coordinates document classification execution and persistence.
    """

    def __init__(self, db: AsyncSession, llm: LLMProvider) -> None:
        self._db = db
        self._llm = llm

    async def classify_document(self, document_id: uuid.UUID) -> Document:
        """
        Execute the Classification Agent for the given document.

        1. Load document by ID.
        2. Validate OCR has completed.
        3. Append ProcessingHistory record (stage=CLASSIFICATION, status=IN_PROGRESS).
        4. Execute LangGraph classification workflow.
        5. Persist classification result and transition status to CLASSIFIED.
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

        # Ensure document has finished OCR
        if (
            document.status != DocumentStatus.OCR_COMPLETED.value
            and document.status != DocumentStatus.CLASSIFIED.value
        ):
            raise OcrNotCompletedForClassificationError(document_id, document.status)

        if not document.ocr_text or not document.ocr_text.strip():
            raise OcrNotCompletedForClassificationError(document_id, document.status)

        start_time = datetime.now(timezone.utc)

        # Audit record
        history = ProcessingHistory(
            id=uuid.uuid4(),
            document_id=document.id,
            stage=ProcessingStage.CLASSIFICATION.value,
            status=StageStatus.IN_PROGRESS.value,
            message="Starting document classification with LangGraph agent...",
            started_at=start_time,
            completed_at=None,
        )
        self._db.add(history)
        await self._db.flush()

        logger.info(
            "classification.started",
            document_id=str(document.id),
            provider=self._llm.provider_name,
        )

        try:
            # Build and execute the LangGraph workflow
            graph = create_classification_graph(llm_provider=self._llm, db=self._db)

            initial_state: ClassificationState = {
                "document_id": str(document.id),
                "document_text": document.ocr_text,
            }

            final_state: ClassificationState = await graph.ainvoke(initial_state)

            if final_state.get("error"):
                raise ClassificationError(final_state["error"])

            now = datetime.now(timezone.utc)
            document.document_type = final_state.get("document_type")
            document.classification_confidence = final_state.get("confidence")
            document.classification_reasoning = final_state.get("reasoning")
            document.classification_signals = final_state.get("signals")
            document.classified_at = now
            document.status = DocumentStatus.CLASSIFIED.value
            document.error_message = None

            conf_str = (
                f"{document.classification_confidence:.2f}"
                if document.classification_confidence is not None
                else "N/A"
            )
            history.status = StageStatus.COMPLETED.value
            history.completed_at = now
            history.message = (
                f"Classified as {document.document_type} (confidence: {conf_str})."
            )

            await self._db.flush()
            await self._db.refresh(document)

            logger.info(
                "classification.completed",
                document_id=str(document.id),
                document_type=document.document_type,
                confidence=document.classification_confidence,
            )
            return document

        except Exception as exc:
            finish_time = datetime.now(timezone.utc)
            document.status = DocumentStatus.FAILED.value
            document.error_message = f"Classification failed: {str(exc)}"

            history.status = StageStatus.FAILED.value
            history.completed_at = finish_time
            history.error_details = str(exc)
            history.message = f"Classification failed: {str(exc)}"

            await self._db.flush()
            await self._db.refresh(document)

            logger.error(
                "classification.failed",
                document_id=str(document.id),
                error=str(exc),
            )
            if isinstance(exc, ClassificationServiceError):
                raise
            raise ClassificationError(f"Classification failed: {str(exc)}") from exc

    async def get_classification(self, document_id: uuid.UUID) -> Document:
        """
        Retrieve a classified document.

        Raises:
        - DocumentNotFoundError if document does not exist.
        - DocumentNotClassifiedError if document has not been classified.
        """
        stmt = select(Document).where(Document.id == document_id)
        result = await self._db.execute(stmt)
        document = result.scalar_one_or_none()

        if document is None:
            raise DocumentNotFoundError(document_id)

        if document.status != DocumentStatus.CLASSIFIED.value and not document.document_type:
            raise DocumentNotClassifiedError(document_id, document.status)

        return document
