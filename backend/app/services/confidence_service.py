"""
services/confidence_service.py
==============================
Business logic for confidence calculation and approval routing.

Computes a multi-factor confidence score based on:
1. Classification confidence (weight: 0.25)
2. Extraction completeness (weight: 0.35)
3. Validation score (weight: 0.40)

Routes document to:
- APPROVED (AUTO_APPROVE) if overall_confidence >= AUTO_APPROVAL_THRESHOLD and validation passed
- REVIEW_REQUIRED otherwise
"""

from __future__ import annotations

import datetime
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import (
    ConfidenceRecommendation,
    DocumentStatus,
    ProcessingStage,
    StageStatus,
)
from app.core.logging import get_logger
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.schemas.confidence import ConfidenceResponse

logger = get_logger("app.services.confidence")


class ConfidenceServiceError(Exception):
    """Base exception for confidence scoring errors."""


class DocumentNotFoundError(ConfidenceServiceError):
    """Raised when document is not found by ID."""


class ValidationNotCompletedForConfidenceError(ConfidenceServiceError):
    """Raised when confidence scoring is triggered before validation completes."""


class ConfidenceNotCalculatedError(ConfidenceServiceError):
    """Raised when confidence result is requested before scoring runs."""


class ConfidenceScoringError(ConfidenceServiceError):
    """Raised when confidence scoring calculation encounters an error."""


EXPECTED_FIELDS_BY_DOC_TYPE: dict[str, list[str]] = {
    "INVOICE": ["invoice_number", "invoice_date", "vendor", "total_amount", "line_items"],
    "RECEIPT": ["merchant", "transaction_date", "total_amount", "items"],
    "PURCHASE_ORDER": ["po_number", "po_date", "buyer", "supplier", "total_amount", "line_items"],
    "CONTRACT": ["contract_title", "parties", "effective_date"],
    "OTHER": ["title", "summary"],
}


def compute_extraction_completeness(
    document_type: str | None,
    extracted_data: dict[str, Any] | None,
) -> float:
    """
    Calculate completeness score (0.0 to 1.0) based on populated expected fields.
    """
    if not extracted_data or not isinstance(extracted_data, dict):
        return 0.0

    doc_type_upper = (document_type or "OTHER").upper()
    expected_fields = EXPECTED_FIELDS_BY_DOC_TYPE.get(
        doc_type_upper,
        ["title", "summary"],
    )

    present_count = 0
    for field in expected_fields:
        val = extracted_data.get(field)
        if field == "supplier" and val is None:
            val = extracted_data.get("vendor")

        if val is not None:
            if isinstance(val, (list, dict, str)) and len(val) == 0:
                continue
            present_count += 1

    return round(present_count / max(1, len(expected_fields)), 4)


class ConfidenceService:
    """
    Computes overall confidence, assigns recommendations, updates document status,
    and logs stage history.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_document(self, document_id: uuid.UUID) -> Document:
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        return document

    async def calculate_confidence(self, document_id: uuid.UUID) -> ConfidenceResponse:
        """
        Calculate overall confidence score and determine routing recommendation.

        Prerequisites:
            - Document must exist
            - Document must have completed validation
        """
        document = await self._get_document(document_id)

        if document.validation_result is None or document.validation_score is None:
            raise ValidationNotCompletedForConfidenceError(
                f"Document {document_id} cannot be scored for confidence: validation has not completed."
            )

        history = ProcessingHistory(
            document_id=document.id,
            stage=ProcessingStage.CONFIDENCE_SCORING.value,
            status=StageStatus.IN_PROGRESS.value,
            started_at=datetime.datetime.now(datetime.timezone.utc),
            message="Confidence scoring initiated",
        )
        self.db.add(history)
        await self.db.commit()

        start_time = time.monotonic()
        logger.info("confidence_scoring_started", document_id=str(document_id))

        try:
            # Factor 1: Classification Confidence (default to 0.85 if unpopulated)
            class_conf = float(
                document.classification_confidence
                if document.classification_confidence is not None
                else 0.85
            )

            # Factor 2: Extraction Completeness
            extract_comp = compute_extraction_completeness(
                document.document_type,
                document.extracted_data,
            )

            # Factor 3: Validation Confidence
            val_conf = float(document.validation_score)

            # Transparent formula: 25% classification, 35% extraction, 40% validation
            w_class, w_extract, w_val = 0.25, 0.35, 0.40
            overall = round(
                (w_class * class_conf) + (w_extract * extract_comp) + (w_val * val_conf),
                4,
            )
            overall = max(0.0, min(1.0, overall))

            factors = {
                "weights": {
                    "classification": w_class,
                    "extraction": w_extract,
                    "validation": w_val,
                },
                "scores": {
                    "classification_confidence": class_conf,
                    "extraction_completeness": extract_comp,
                    "validation_score": val_conf,
                },
                "thresholds": {
                    "auto_approval_threshold": settings.AUTO_APPROVAL_THRESHOLD,
                    "review_threshold": settings.REVIEW_THRESHOLD,
                },
            }

            # Recommendation and Routing Decision
            val_is_valid = bool((document.validation_result or {}).get("is_valid", False))
            if overall >= settings.AUTO_APPROVAL_THRESHOLD and val_is_valid:
                recommendation = ConfidenceRecommendation.AUTO_APPROVE.value
                new_status = DocumentStatus.APPROVED.value
            else:
                recommendation = ConfidenceRecommendation.REVIEW_REQUIRED.value
                new_status = DocumentStatus.REVIEW_REQUIRED.value

            now = datetime.datetime.now(datetime.timezone.utc)
            duration_ms = int((time.monotonic() - start_time) * 1000)

            document.overall_confidence = overall
            document.extraction_confidence = extract_comp
            document.validation_confidence = val_conf
            document.confidence_recommendation = recommendation
            document.confidence_factors = factors
            document.confidence_calculated_at = now
            document.status = new_status

            history.status = StageStatus.COMPLETED.value
            history.completed_at = now
            history.duration_ms = duration_ms
            history.message = (
                f"Confidence scored: {overall} -> {recommendation} (Status: {new_status})"
            )

            await self.db.commit()
            await self.db.refresh(document)

            # Automatic review creation for human-in-the-loop queue (Step 8 Part D)
            if recommendation == ConfidenceRecommendation.REVIEW_REQUIRED.value:
                from app.services.review_service import DuplicateReviewError, ReviewService
                review_service = ReviewService(self.db)
                try:
                    await review_service.create_review(document.id)
                except DuplicateReviewError:
                    pass
            elif recommendation == ConfidenceRecommendation.AUTO_APPROVE.value:
                # Step 9 Part G: Index approved document into vector database
                from app.services.rag.ingestion import RagIngestionService
                try:
                    rag_service = RagIngestionService(self.db)
                    await rag_service.index_document(document.id)
                except Exception as index_err:
                    logger.warning(
                        "auto_indexing_failed",
                        document_id=str(document_id),
                        error=str(index_err),
                    )

            logger.info(
                "confidence_scoring_completed",
                document_id=str(document_id),
                overall_confidence=overall,
                recommendation=recommendation,
                new_status=new_status,
                duration_ms=duration_ms,
            )

            return ConfidenceResponse(
                document_id=document.id,
                overall_confidence=overall,
                classification_confidence=class_conf,
                extraction_confidence=extract_comp,
                validation_confidence=val_conf,
                recommendation=recommendation,
                confidence_factors=factors,
                status=document.status,
                calculated_at=document.confidence_calculated_at,
            )

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            history.status = StageStatus.FAILED.value
            history.completed_at = datetime.datetime.now(datetime.timezone.utc)
            history.duration_ms = duration_ms
            history.error_details = str(exc)
            history.message = f"Confidence scoring failed: {exc}"

            document.status = DocumentStatus.FAILED.value
            document.error_message = f"Confidence scoring error: {exc}"

            await self.db.commit()
            logger.error(
                "confidence_scoring_failed",
                document_id=str(document_id),
                error=str(exc),
                duration_ms=duration_ms,
            )

            if isinstance(exc, ConfidenceServiceError):
                raise
            raise ConfidenceScoringError(str(exc)) from exc

    async def get_confidence(self, document_id: uuid.UUID) -> ConfidenceResponse:
        """Retrieve the latest confidence scoring result for a scored document."""
        document = await self._get_document(document_id)
        if document.overall_confidence is None:
            raise ConfidenceNotCalculatedError(
                f"Document {document_id} has not yet completed confidence scoring."
            )

        return ConfidenceResponse(
            document_id=document.id,
            overall_confidence=document.overall_confidence,
            classification_confidence=document.classification_confidence or 0.0,
            extraction_confidence=document.extraction_confidence or 0.0,
            validation_confidence=document.validation_confidence or 0.0,
            recommendation=document.confidence_recommendation or "",
            confidence_factors=document.confidence_factors or {},
            status=document.status,
            calculated_at=document.confidence_calculated_at,
        )
