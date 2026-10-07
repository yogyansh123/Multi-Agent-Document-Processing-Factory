"""
services/validation_service.py
==============================
Business logic for document validation orchestration.

Validates that OCR, Classification, and Information Extraction have completed,
manages ProcessingHistory stage records, executes the LangGraph validation agent,
and updates Document status to VALIDATED or FAILED.
"""

from __future__ import annotations

import datetime
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.validation.graph import create_validation_graph
from app.agents.validation.schemas import ValidationIssue
from app.core.enums import DocumentStatus, ProcessingStage, StageStatus
from app.core.logging import get_logger
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.schemas.validation import ValidationResponse
from app.services.llm.base import LLMProvider

logger = get_logger("app.services.validation")


class ValidationServiceError(Exception):
    """Base exception for validation service errors."""


class DocumentNotFoundError(ValidationServiceError):
    """Raised when a document is not found by ID."""


class OcrNotCompletedForValidationError(ValidationServiceError):
    """Raised when validation is triggered before OCR completes."""


class ClassificationNotCompletedForValidationError(ValidationServiceError):
    """Raised when validation is triggered before classification completes."""


class ExtractionNotCompletedForValidationError(ValidationServiceError):
    """Raised when validation is triggered before information extraction completes."""


class DocumentNotValidatedError(ValidationServiceError):
    """Raised when requesting validation results for a document that hasn't been validated."""


class ValidationError(ValidationServiceError):
    """Raised when the validation agent encounters an unrecoverable failure."""


class ValidationService:
    """
    Coordinates document validation execution, state persistence, and history logging.
    """

    def __init__(self, db: AsyncSession, llm_provider: LLMProvider | None = None) -> None:
        self.db = db
        self.llm_provider = llm_provider

    async def _get_document(self, document_id: uuid.UUID) -> Document:
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        return document

    async def validate_document(self, document_id: uuid.UUID) -> ValidationResponse:
        """
        Execute deterministic and semantic validation for a document.

        Prerequisites:
            - Document must exist
            - OCR text must be present
            - Document must be classified
            - Extracted data must be present
        """
        document = await self._get_document(document_id)

        # Enforce pipeline sequence
        if not document.ocr_text:
            raise OcrNotCompletedForValidationError(
                f"Document {document_id} cannot be validated: OCR has not completed."
            )
        if not document.document_type:
            raise ClassificationNotCompletedForValidationError(
                f"Document {document_id} cannot be validated: document has not been classified."
            )
        if document.extracted_data is None:
            raise ExtractionNotCompletedForValidationError(
                f"Document {document_id} cannot be validated: information extraction has not completed."
            )

        # Audit log stage record
        history = ProcessingHistory(
            document_id=document.id,
            stage=ProcessingStage.VALIDATION.value,
            status=StageStatus.IN_PROGRESS.value,
            started_at=datetime.datetime.now(datetime.timezone.utc),
            message="Document validation initiated",
        )
        self.db.add(history)
        document.status = DocumentStatus.PROCESSING.value
        await self.db.commit()

        start_time = time.monotonic()
        logger.info(
            "validation_started",
            document_id=str(document_id),
            document_type=document.document_type,
        )

        try:
            graph = create_validation_graph(llm_provider=self.llm_provider, db=self.db)
            final_state = await graph.ainvoke(
                {
                    "document_id": str(document.id),
                    "document_text": document.ocr_text,
                    "document_type": document.document_type,
                    "extracted_data": document.extracted_data,
                }
            )

            error = final_state.get("error")
            if error:
                raise ValidationError(f"Validation agent failed: {error}")

            # Reload document with fresh attributes committed by graph node
            await self.db.refresh(document)

            duration_ms = int((time.monotonic() - start_time) * 1000)
            now = datetime.datetime.now(datetime.timezone.utc)

            history.status = StageStatus.COMPLETED.value
            history.completed_at = now
            history.duration_ms = duration_ms
            history.message = (
                f"Validation completed. Valid: {final_state.get('is_valid')}, "
                f"Score: {document.validation_score}"
            )
            document.status = DocumentStatus.VALIDATED.value
            await self.db.commit()
            await self.db.refresh(document)

            logger.info(
                "validation_completed",
                document_id=str(document_id),
                is_valid=final_state.get("is_valid"),
                validation_score=document.validation_score,
                duration_ms=duration_ms,
            )

            raw_issues = (document.validation_result or {}).get("issues", [])
            issues = [ValidationIssue(**iss) for iss in raw_issues]
            rules_checked = (document.validation_result or {}).get("rules_checked", [])

            return ValidationResponse(
                document_id=document.id,
                document_type=document.document_type,
                is_valid=bool((document.validation_result or {}).get("is_valid", False)),
                validation_score=document.validation_score or 0.0,
                issues=issues,
                rules_checked=rules_checked,
                status=document.status,
                validated_at=document.validated_at,
            )

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            history.status = StageStatus.FAILED.value
            history.completed_at = datetime.datetime.now(datetime.timezone.utc)
            history.duration_ms = duration_ms
            history.error_details = str(exc)
            history.message = f"Validation failed: {exc}"

            document.status = DocumentStatus.FAILED.value
            document.error_message = f"Validation error: {exc}"

            await self.db.commit()
            logger.error(
                "validation_failed",
                document_id=str(document_id),
                error=str(exc),
                duration_ms=duration_ms,
            )

            if isinstance(exc, ValidationServiceError):
                raise
            raise ValidationError(str(exc)) from exc

    async def get_validation(self, document_id: uuid.UUID) -> ValidationResponse:
        """Retrieve the latest validation result for a validated document."""
        document = await self._get_document(document_id)
        if document.validation_result is None or document.validation_score is None:
            raise DocumentNotValidatedError(
                f"Document {document_id} has not yet been validated."
            )

        raw_issues = (document.validation_result or {}).get("issues", [])
        issues = [ValidationIssue(**iss) for iss in raw_issues]
        rules_checked = (document.validation_result or {}).get("rules_checked", [])

        return ValidationResponse(
            document_id=document.id,
            document_type=document.document_type,
            is_valid=bool((document.validation_result or {}).get("is_valid", False)),
            validation_score=document.validation_score,
            issues=issues,
            rules_checked=rules_checked,
            status=document.status,
            validated_at=document.validated_at,
        )
