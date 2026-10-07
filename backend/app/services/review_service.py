"""
services/review_service.py
==========================
Human-in-the-Loop review management service.

Handles:
- Automatic and manual review creation
- Review queue retrieval with filtering and pagination
- Review lifecycle transitions: PENDING -> IN_REVIEW -> COMPLETED (APPROVED / REJECTED / CORRECTED)
- Structured extraction correction with schema validation and deterministic revalidation
- Audit history logging (ProcessingStage.HUMAN_REVIEW)
- Atomic transactions and race-condition prevention
- Redis cache invalidation
"""

from __future__ import annotations

import datetime
import math
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.extraction.schemas import get_extraction_schema
from app.agents.validation.rules import validate_deterministic
from app.core.config import settings
from app.core.enums import (
    ConfidenceRecommendation,
    DocumentStatus,
    ProcessingStage,
    ReviewDecision,
    ReviewStatus,
    StageStatus,
    ValidationSeverity,
)
from app.core.logging import get_logger
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.models.review import DocumentReview
from app.schemas.review import (
    ReviewDocumentDetails,
    ReviewQueueItem,
    ReviewQueueResponse,
)
from app.services.cache import RedisService
from app.services.confidence_service import compute_extraction_completeness

logger = get_logger("app.services.review")


class ReviewServiceError(Exception):
    """Base exception for review service errors."""


class ReviewNotFoundError(ReviewServiceError):
    """Raised when review is not found by ID."""


class DocumentNotFoundError(ReviewServiceError):
    """Raised when document associated with review is not found."""


class DocumentNotEligibleForReviewError(ReviewServiceError):
    """Raised when document does not require human review."""


class DuplicateReviewError(ReviewServiceError):
    """Raised when an active review already exists for a document."""


class InvalidReviewStateError(ReviewServiceError):
    """Raised when an invalid review transition is attempted."""


class ReviewValidationError(ReviewServiceError):
    """Raised when human-corrected data fails Pydantic schema validation."""


class ReviewService:
    """
    Manages document reviews, queue queries, and lifecycle actions.
    """

    def __init__(
        self,
        db: AsyncSession,
        redis_service: RedisService | None = None,
    ) -> None:
        self.db = db
        self.redis_service = redis_service

    async def _invalidate_cache(self, document_id: uuid.UUID | str) -> None:
        """Best-effort invalidation of the document status cache."""
        if self.redis_service:
            try:
                await self.redis_service.delete_document_status(document_id)
            except Exception as exc:
                logger.warning(
                    "redis_cache_invalidation_failed",
                    document_id=str(document_id),
                    error=str(exc),
                )

    async def create_review(self, document_id: uuid.UUID) -> DocumentReview:
        """
        Create a new PENDING review for a document requiring review.

        Prerequisites:
        - Document must exist
        - Document must have confidence_recommendation == REVIEW_REQUIRED
        - No active review (PENDING or IN_REVIEW) must already exist for this document
        """
        # Fetch document
        doc_stmt = select(Document).where(Document.id == document_id)
        doc_result = await self.db.execute(doc_stmt)
        document = doc_result.scalar_one_or_none()

        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        # Eligibility check: only REVIEW_REQUIRED documents should enter queue
        if document.confidence_recommendation != ConfidenceRecommendation.REVIEW_REQUIRED.value:
            raise DocumentNotEligibleForReviewError(
                f"Document {document_id} is not eligible for review. "
                f"Recommendation is {document.confidence_recommendation}, expected REVIEW_REQUIRED."
            )

        # Check for existing active review
        active_stmt = select(DocumentReview).where(
            DocumentReview.document_id == document_id,
            DocumentReview.status.in_([ReviewStatus.PENDING.value, ReviewStatus.IN_REVIEW.value]),
        )
        active_result = await self.db.execute(active_stmt)
        existing_active = active_result.scalar_one_or_none()

        if existing_active:
            raise DuplicateReviewError(
                f"An active review ({existing_active.id}) already exists for document {document_id} "
                f"with status {existing_active.status}."
            )

        # Build snapshots
        confidence_snapshot = {
            "overall_confidence": document.overall_confidence,
            "classification_confidence": document.classification_confidence,
            "extraction_confidence": document.extraction_confidence,
            "validation_confidence": document.validation_confidence,
            "confidence_recommendation": document.confidence_recommendation,
            "confidence_factors": document.confidence_factors,
        }

        review = DocumentReview(
            document_id=document.id,
            status=ReviewStatus.PENDING.value,
            original_extracted_data=document.extracted_data or {},
            validation_result_snapshot=document.validation_result,
            confidence_snapshot=confidence_snapshot,
        )

        try:
            self.db.add(review)
            await self.db.commit()
            await self.db.refresh(review)
            logger.info("review_created", review_id=str(review.id), document_id=str(document_id))
            return review
        except Exception:
            await self.db.rollback()
            raise

    async def get_review(self, review_id: uuid.UUID) -> DocumentReview:
        """
        Retrieve a single review by ID with document and history eagerly loaded.
        """
        stmt = (
            select(DocumentReview)
            .where(DocumentReview.id == review_id)
            .options(
                selectinload(DocumentReview.document).selectinload(Document.processing_history)
            )
        )
        result = await self.db.execute(stmt)
        review = result.scalar_one_or_none()

        if not review:
            raise ReviewNotFoundError(f"Review {review_id} not found")

        return review

    async def list_pending_reviews(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        document_type: str | None = None,
    ) -> ReviewQueueResponse:
        """
        List paginated review queue items with optional status and document_type filtering.
        """
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size

        # Base query joining DocumentReview and Document
        base_query = (
            select(DocumentReview)
            .join(Document, DocumentReview.document_id == Document.id)
            .options(selectinload(DocumentReview.document))
        )

        count_query = (
            select(func.count(DocumentReview.id))
            .join(Document, DocumentReview.document_id == Document.id)
        )

        # Filter by status
        if status:
            status_clean = status.strip().upper()
            if status_clean != "ALL":
                base_query = base_query.where(DocumentReview.status == status_clean)
                count_query = count_query.where(DocumentReview.status == status_clean)
        else:
            # Default to active pending/in_review queue items
            base_query = base_query.where(DocumentReview.status == ReviewStatus.PENDING.value)
            count_query = count_query.where(DocumentReview.status == ReviewStatus.PENDING.value)

        # Filter by document type
        if document_type:
            doc_type_clean = document_type.strip().upper()
            base_query = base_query.where(Document.document_type == doc_type_clean)
            count_query = count_query.where(Document.document_type == doc_type_clean)

        # Count total
        total_res = await self.db.execute(count_query)
        total = total_res.scalar() or 0

        # Fetch page items
        query = (
            base_query.order_by(DocumentReview.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        res = await self.db.execute(query)
        reviews = res.scalars().all()

        items: list[ReviewQueueItem] = []
        for r in reviews:
            doc = r.document
            items.append(
                ReviewQueueItem(
                    review_id=r.id,
                    document_id=r.document_id,
                    original_filename=doc.original_filename if doc else "unknown",
                    document_type=doc.document_type if doc else None,
                    status=r.status,
                    overall_confidence=doc.overall_confidence if doc else None,
                    confidence_recommendation=doc.confidence_recommendation if doc else None,
                    validation_score=doc.validation_score if doc else None,
                    created_at=r.created_at,
                )
            )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return ReviewQueueResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def start_review(
        self,
        review_id: uuid.UUID,
        reviewer_name: str | None = None,
        reviewer_id: str | None = None,
    ) -> DocumentReview:
        """
        Transition a review from PENDING to IN_REVIEW.

        Prevent invalid transitions (e.g. COMPLETED -> IN_REVIEW).
        """
        review = await self.get_review(review_id)

        if review.status == ReviewStatus.COMPLETED.value:
            raise InvalidReviewStateError(
                f"Cannot start review {review_id}: review is already COMPLETED."
            )

        try:
            review.status = ReviewStatus.IN_REVIEW.value
            if reviewer_name:
                review.reviewer_name = reviewer_name
            if reviewer_id:
                review.reviewer_id = reviewer_id

            history = ProcessingHistory(
                document_id=review.document_id,
                stage=ProcessingStage.HUMAN_REVIEW.value,
                status=StageStatus.IN_PROGRESS.value,
                started_at=datetime.datetime.now(datetime.timezone.utc),
                message=f"Review started by {reviewer_name or 'reviewer'}",
            )
            self.db.add(history)

            await self.db.commit()
            await self.db.refresh(review)
            logger.info("review_started", review_id=str(review_id), reviewer=reviewer_name)
            return review
        except Exception:
            await self.db.rollback()
            raise

    async def approve_review(
        self,
        review_id: uuid.UUID,
        reason: str | None = None,
        reviewer_name: str | None = None,
        reviewer_id: str | None = None,
    ) -> DocumentReview:
        """
        Approve a review without modifying extraction.

        Transitions:
        - Review: PENDING / IN_REVIEW -> COMPLETED, decision: APPROVED
        - Document: REVIEW_REQUIRED -> APPROVED
        - ProcessingHistory: completed human review stage
        - Invalidate Redis status cache
        """
        review = await self.get_review(review_id)

        if review.status == ReviewStatus.COMPLETED.value:
            raise InvalidReviewStateError(
                f"Cannot approve review {review_id}: review is already COMPLETED with decision {review.decision}."
            )

        document = review.document
        if not document:
            raise DocumentNotFoundError(f"Document {review.document_id} not found")

        now = datetime.datetime.now(datetime.timezone.utc)

        try:
            # 1. Update review
            review.status = ReviewStatus.COMPLETED.value
            review.decision = ReviewDecision.APPROVED.value
            review.reviewed_at = now
            if reason:
                review.reason = reason
            if reviewer_name:
                review.reviewer_name = reviewer_name
            if reviewer_id:
                review.reviewer_id = reviewer_id

            # 2. Update document
            document.status = DocumentStatus.APPROVED.value

            # 3. Add ProcessingHistory audit entry
            history = ProcessingHistory(
                document_id=document.id,
                stage=ProcessingStage.HUMAN_REVIEW.value,
                status=StageStatus.COMPLETED.value,
                started_at=review.created_at,
                completed_at=now,
                message=f"Human review approved: {reason or 'AI extraction confirmed'}",
            )
            self.db.add(history)

            await self.db.commit()
            await self.db.refresh(review)
            await self.db.refresh(document)

            logger.info(
                "review_approved",
                review_id=str(review_id),
                document_id=str(document.id),
                reviewer=reviewer_name,
            )

            # Invalidate Redis cache
            await self._invalidate_cache(document.id)

            # Auto-index in RAG upon human approval (Step 9 Part G)
            try:
                from app.services.rag.ingestion import RagIngestionService
                rag_service = RagIngestionService(self.db)
                await rag_service.index_document(document.id)
            except Exception as rag_err:
                logger.warning(
                    "rag_indexing_after_approval_failed",
                    document_id=str(document.id),
                    error=str(rag_err),
                )

            return review
        except Exception:
            await self.db.rollback()
            raise

    async def reject_review(
        self,
        review_id: uuid.UUID,
        reason: str | None = None,
        reviewer_name: str | None = None,
        reviewer_id: str | None = None,
    ) -> DocumentReview:
        """
        Reject a document review.

        Transitions:
        - Review: PENDING / IN_REVIEW -> COMPLETED, decision: REJECTED
        - Document: REVIEW_REQUIRED -> REJECTED
        - ProcessingHistory: failed human review stage
        - Invalidate Redis status cache
        """
        review = await self.get_review(review_id)

        if review.status == ReviewStatus.COMPLETED.value:
            raise InvalidReviewStateError(
                f"Cannot reject review {review_id}: review is already COMPLETED with decision {review.decision}."
            )

        document = review.document
        if not document:
            raise DocumentNotFoundError(f"Document {review.document_id} not found")

        now = datetime.datetime.now(datetime.timezone.utc)

        try:
            # 1. Update review
            review.status = ReviewStatus.COMPLETED.value
            review.decision = ReviewDecision.REJECTED.value
            review.reviewed_at = now
            if reason:
                review.reason = reason
            if reviewer_name:
                review.reviewer_name = reviewer_name
            if reviewer_id:
                review.reviewer_id = reviewer_id

            # 2. Update document status to REJECTED
            document.status = DocumentStatus.REJECTED.value

            # 3. Add ProcessingHistory audit entry
            history = ProcessingHistory(
                document_id=document.id,
                stage=ProcessingStage.HUMAN_REVIEW.value,
                status=StageStatus.FAILED.value,
                started_at=review.created_at,
                completed_at=now,
                message=f"Human review rejected: {reason or 'Rejected by reviewer'}",
                error_details=reason,
            )
            self.db.add(history)

            await self.db.commit()
            await self.db.refresh(review)
            await self.db.refresh(document)

            logger.info(
                "review_rejected",
                review_id=str(review_id),
                document_id=str(document.id),
                reason=reason,
            )

            # Invalidate Redis cache
            await self._invalidate_cache(document.id)

            # Remove from RAG corpus if previously indexed (Step 9 Part G)
            try:
                from app.services.rag.ingestion import RagIngestionService
                rag_service = RagIngestionService(self.db)
                await rag_service.remove_document_index(document.id)
            except Exception as rag_err:
                logger.warning(
                    "rag_removal_after_rejection_failed",
                    document_id=str(document.id),
                    error=str(rag_err),
                )

            return review
        except Exception:
            await self.db.rollback()
            raise

    async def correct_review(
        self,
        review_id: uuid.UUID,
        corrected_data: dict[str, Any],
        reason: str | None = None,
        reviewer_name: str | None = None,
        reviewer_id: str | None = None,
    ) -> DocumentReview:
        """
        Submit human corrections to structured extraction.

        Flow:
        1. Validate corrected_data against document-type-specific Pydantic schema.
        2. Preserve original AI extraction in review.original_extracted_data.
        3. Save reviewed extraction in review.reviewed_extracted_data.
        4. Update document.extracted_data to corrected version.
        5. Re-run deterministic validation against corrected extraction.
        6. Recalculate confidence score.
        7. If passes validation, document status -> APPROVED.
        8. Review status -> COMPLETED, decision -> CORRECTED.
        9. Record ProcessingHistory audit entry.
        10. Invalidate Redis cache.
        """
        review = await self.get_review(review_id)

        if review.status == ReviewStatus.COMPLETED.value:
            raise InvalidReviewStateError(
                f"Cannot correct review {review_id}: review is already COMPLETED with decision {review.decision}."
            )

        document = review.document
        if not document:
            raise DocumentNotFoundError(f"Document {review.document_id} not found")

        # 1. Pydantic schema validation against document type
        schema_cls = get_extraction_schema(document.document_type or "OTHER")
        try:
            validated_obj = schema_cls.model_validate(corrected_data)
            validated_dict = validated_obj.model_dump(mode="json")
        except Exception as exc:
            logger.warning(
                "correction_schema_validation_failed",
                review_id=str(review_id),
                doc_type=document.document_type,
                error=str(exc),
            )
            raise ReviewValidationError(
                f"Corrected data failed schema validation for {document.document_type}: {exc}"
            ) from exc

        now = datetime.datetime.now(datetime.timezone.utc)

        try:
            # 2. Re-run deterministic validation on corrected data
            issues, rules_checked = validate_deterministic(
                document.document_type or "OTHER",
                validated_dict,
                settings.ARITHMETIC_TOLERANCE,
            )

            # Score deterministic validation
            error_count = sum(1 for iss in issues if iss.severity == ValidationSeverity.ERROR)
            warning_count = sum(1 for iss in issues if iss.severity == ValidationSeverity.WARNING)
            info_count = sum(1 for iss in issues if iss.severity == ValidationSeverity.INFO)

            penalty = (error_count * 0.25) + (warning_count * 0.08) + (info_count * 0.02)
            deterministic_score = max(0.0, min(1.0, round(1.0 - penalty, 4)))

            # Semantic component defaults to 1.0 for manual human correction
            semantic_score = 1.0
            composite_val_score = round((0.70 * deterministic_score) + (0.30 * semantic_score), 4)
            composite_val_score = max(0.0, min(1.0, composite_val_score))

            is_valid = error_count == 0

            val_result = {
                "is_valid": is_valid,
                "issues": [iss.model_dump() for iss in issues],
                "rules_checked": rules_checked,
                "validation_score": composite_val_score,
            }

            # 3. Recalculate confidence
            class_conf = float(
                document.classification_confidence
                if document.classification_confidence is not None
                else 0.85
            )
            extract_comp = compute_extraction_completeness(
                document.document_type,
                validated_dict,
            )
            w_class, w_extract, w_val = 0.25, 0.35, 0.40
            overall = round(
                (w_class * class_conf) + (w_extract * extract_comp) + (w_val * composite_val_score),
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
                    "validation_score": composite_val_score,
                },
                "thresholds": {
                    "auto_approval_threshold": settings.AUTO_APPROVAL_THRESHOLD,
                    "review_threshold": settings.REVIEW_THRESHOLD,
                },
                "correction_applied": True,
            }

            # 4. Preserve original AI extraction on review, set reviewed extraction
            if not review.original_extracted_data:
                review.original_extracted_data = document.extracted_data or {}
            review.reviewed_extracted_data = validated_dict

            # 5. Update document extraction, validation, and confidence
            document.extracted_data = validated_dict
            document.validation_score = composite_val_score
            document.validation_result = val_result
            document.overall_confidence = overall
            document.extraction_confidence = extract_comp
            document.validation_confidence = composite_val_score
            document.confidence_factors = factors

            # 6. Status determination: if valid, approve document
            if is_valid:
                document.status = DocumentStatus.APPROVED.value
                document.confidence_recommendation = ConfidenceRecommendation.AUTO_APPROVE.value
            else:
                # If still has errors after correction, keep in review required
                document.status = DocumentStatus.REVIEW_REQUIRED.value

            # 7. Update review lifecycle
            review.status = ReviewStatus.COMPLETED.value
            review.decision = ReviewDecision.CORRECTED.value
            review.reviewed_at = now
            if reason:
                review.reason = reason
            if reviewer_name:
                review.reviewer_name = reviewer_name
            if reviewer_id:
                review.reviewer_id = reviewer_id

            # 8. Add ProcessingHistory audit entry
            history = ProcessingHistory(
                document_id=document.id,
                stage=ProcessingStage.HUMAN_REVIEW.value,
                status=StageStatus.COMPLETED.value,
                started_at=review.created_at,
                completed_at=now,
                message=f"Human corrections applied: {reason or 'Structured fields updated'} (Valid: {is_valid}, Score: {composite_val_score})",
            )
            self.db.add(history)

            await self.db.commit()
            await self.db.refresh(review)
            await self.db.refresh(document)

            logger.info(
                "review_corrected",
                review_id=str(review_id),
                document_id=str(document.id),
                is_valid=is_valid,
                new_validation_score=composite_val_score,
                new_confidence=overall,
            )

            # Invalidate Redis cache
            await self._invalidate_cache(document.id)

            # Re-index in RAG if correction approved document (Step 9 Part G)
            if is_valid:
                try:
                    from app.services.rag.ingestion import RagIngestionService
                    rag_service = RagIngestionService(self.db)
                    await rag_service.index_document(document.id)
                except Exception as rag_err:
                    logger.warning(
                        "rag_indexing_after_correction_failed",
                        document_id=str(document.id),
                        error=str(rag_err),
                    )

            return review
        except Exception:
            await self.db.rollback()
            raise
