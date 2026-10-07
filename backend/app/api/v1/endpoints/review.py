"""
api/v1/endpoints/review.py
==========================
Human-in-the-Loop review API endpoints.

Routes:
- GET  /api/v1/review/queue
- GET  /api/v1/review/{review_id}
- POST /api/v1/review/{review_id}/start
- POST /api/v1/review/{review_id}/approve
- POST /api/v1/review/{review_id}/reject
- POST /api/v1/review/{review_id}/correct
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import Cache, DbSession
from app.schemas.processing_history import ProcessingHistoryResponse
from app.schemas.review import (
    CorrectionRequest,
    ReviewActionResponse,
    ReviewDecisionRequest,
    ReviewDetailsResponse,
    ReviewDocumentDetails,
    ReviewQueueResponse,
)
from app.services.review_service import (
    DocumentNotFoundError,
    DocumentNotEligibleForReviewError,
    DuplicateReviewError,
    InvalidReviewStateError,
    ReviewNotFoundError,
    ReviewService,
    ReviewValidationError,
)

router = APIRouter()


@router.get(
    "/queue",
    response_model=ReviewQueueResponse,
    status_code=status.HTTP_200_OK,
    summary="Get pending review queue",
    description="Returns a paginated list of documents requiring human review with optional status and document type filters.",
)
async def get_review_queue(
    db: DbSession,
    cache: Cache,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    status: Annotated[str | None, Query(description="Filter by review status (e.g. PENDING, IN_REVIEW, COMPLETED, ALL)")] = None,
    document_type: Annotated[str | None, Query(description="Filter by document type (e.g. INVOICE, RECEIPT)")] = None,
) -> ReviewQueueResponse:
    """Retrieve review queue items with pagination and filtering."""
    review_service = ReviewService(db=db, redis_service=cache)
    return await review_service.list_pending_reviews(
        page=page,
        page_size=page_size,
        status=status,
        document_type=document_type,
    )


@router.get(
    "/{review_id}",
    response_model=ReviewDetailsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get review details",
    description="Returns complete details for a review including document metadata, OCR text, extraction, validation, and confidence results.",
)
async def get_review_details(
    review_id: uuid.UUID,
    db: DbSession,
    cache: Cache,
) -> ReviewDetailsResponse:
    """Retrieve all information required for reviewing a document."""
    review_service = ReviewService(db=db, redis_service=cache)
    try:
        review = await review_service.get_review(review_id)
    except ReviewNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    doc = review.document
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated document for review {review_id} not found.",
        )

    doc_details = ReviewDocumentDetails(
        id=doc.id,
        original_filename=doc.original_filename,
        file_type=doc.file_type,
        mime_type=doc.mime_type,
        file_size=doc.file_size,
        document_type=doc.document_type,
        status=doc.status,
        ocr_text=doc.ocr_text,
        classification_confidence=doc.classification_confidence,
        classification_reasoning=doc.classification_reasoning,
        extracted_data=doc.extracted_data,
        validation_score=doc.validation_score,
        validation_result=doc.validation_result,
        overall_confidence=doc.overall_confidence,
        confidence_recommendation=doc.confidence_recommendation,
        confidence_factors=doc.confidence_factors,
    )

    history_items = [
        ProcessingHistoryResponse.model_validate(h)
        for h in (doc.processing_history or [])
    ]

    return ReviewDetailsResponse(
        review_id=review.id,
        document_id=review.document_id,
        status=review.status,
        reviewer_id=review.reviewer_id,
        reviewer_name=review.reviewer_name,
        decision=review.decision,
        reason=review.reason,
        original_extracted_data=review.original_extracted_data,
        reviewed_extracted_data=review.reviewed_extracted_data,
        validation_result_snapshot=review.validation_result_snapshot,
        confidence_snapshot=review.confidence_snapshot,
        created_at=review.created_at,
        updated_at=review.updated_at,
        reviewed_at=review.reviewed_at,
        document=doc_details,
        history=history_items,
    )


@router.post(
    "/{review_id}/start",
    response_model=ReviewActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Start reviewing document",
    description="Transitions review status from PENDING to IN_REVIEW.",
)
async def start_review(
    review_id: uuid.UUID,
    db: DbSession,
    cache: Cache,
    payload: ReviewDecisionRequest | None = None,
) -> ReviewActionResponse:
    """Claim or start a document review."""
    review_service = ReviewService(db=db, redis_service=cache)
    reviewer_name = payload.reviewer_name if payload else None
    try:
        review = await review_service.start_review(
            review_id=review_id,
            reviewer_name=reviewer_name,
        )
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidReviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return ReviewActionResponse(
        review_id=review.id,
        document_id=review.document_id,
        status=review.status,
        decision=review.decision,
        reason=review.reason,
        reviewed_at=review.reviewed_at,
        document_status=review.document.status if review.document else "UNKNOWN",
        message="Review started successfully.",
        validation_score=review.document.validation_score if review.document else None,
        overall_confidence=review.document.overall_confidence if review.document else None,
    )


@router.post(
    "/{review_id}/approve",
    response_model=ReviewActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve review",
    description="Approves document extraction without modification. Sets review to COMPLETED and document to APPROVED.",
)
async def approve_review(
    review_id: uuid.UUID,
    db: DbSession,
    cache: Cache,
    payload: ReviewDecisionRequest | None = None,
) -> ReviewActionResponse:
    """Approve document extraction."""
    review_service = ReviewService(db=db, redis_service=cache)
    reason = payload.reason if payload else None
    reviewer_name = payload.reviewer_name if payload else None

    try:
        review = await review_service.approve_review(
            review_id=review_id,
            reason=reason,
            reviewer_name=reviewer_name,
        )
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidReviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return ReviewActionResponse(
        review_id=review.id,
        document_id=review.document_id,
        status=review.status,
        decision=review.decision,
        reason=review.reason,
        reviewed_at=review.reviewed_at,
        document_status=review.document.status if review.document else "APPROVED",
        message="Review approved successfully.",
        validation_score=review.document.validation_score if review.document else None,
        overall_confidence=review.document.overall_confidence if review.document else None,
    )


@router.post(
    "/{review_id}/reject",
    response_model=ReviewActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject review",
    description="Rejects document extraction. Sets review to COMPLETED and document to REJECTED.",
)
async def reject_review(
    review_id: uuid.UUID,
    db: DbSession,
    cache: Cache,
    payload: ReviewDecisionRequest | None = None,
) -> ReviewActionResponse:
    """Reject document review."""
    review_service = ReviewService(db=db, redis_service=cache)
    reason = payload.reason if payload else None
    reviewer_name = payload.reviewer_name if payload else None

    try:
        review = await review_service.reject_review(
            review_id=review_id,
            reason=reason,
            reviewer_name=reviewer_name,
        )
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidReviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return ReviewActionResponse(
        review_id=review.id,
        document_id=review.document_id,
        status=review.status,
        decision=review.decision,
        reason=review.reason,
        reviewed_at=review.reviewed_at,
        document_status=review.document.status if review.document else "REJECTED",
        message="Review rejected successfully.",
        validation_score=review.document.validation_score if review.document else None,
        overall_confidence=review.document.overall_confidence if review.document else None,
    )


@router.post(
    "/{review_id}/correct",
    response_model=ReviewActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Correct extracted data",
    description="Submits corrected structured extraction, validates schema, re-runs deterministic validation, and updates document.",
)
async def correct_review(
    review_id: uuid.UUID,
    payload: CorrectionRequest,
    db: DbSession,
    cache: Cache,
) -> ReviewActionResponse:
    """Submit human corrections to structured extraction."""
    review_service = ReviewService(db=db, redis_service=cache)
    try:
        review = await review_service.correct_review(
            review_id=review_id,
            corrected_data=payload.corrected_data,
            reason=payload.reason,
            reviewer_name=payload.reviewer_name,
        )
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidReviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ReviewValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    doc = review.document
    return ReviewActionResponse(
        review_id=review.id,
        document_id=review.document_id,
        status=review.status,
        decision=review.decision,
        reason=review.reason,
        reviewed_at=review.reviewed_at,
        document_status=doc.status if doc else "UNKNOWN",
        message="Extraction corrected and validated successfully.",
        validation_score=doc.validation_score if doc else None,
        overall_confidence=doc.overall_confidence if doc else None,
    )
