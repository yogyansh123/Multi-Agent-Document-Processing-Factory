"""
api/v1/endpoints/confidence.py
==============================
FastAPI router for confidence scoring and approval routing endpoints.

Routes:
    POST /documents/{document_id}/confidence — Calculate confidence and route document
    GET  /documents/{document_id}/confidence — Retrieve confidence scoring result
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.core.logging import get_logger
from app.schemas.confidence import ConfidenceResponse
from app.services.confidence_service import (
    ConfidenceNotCalculatedError,
    ConfidenceScoringError,
    ConfidenceService,
    DocumentNotFoundError,
    ValidationNotCompletedForConfidenceError,
)

logger = get_logger("app.api.confidence")

router = APIRouter()


@router.post(
    "/{document_id}/confidence",
    response_model=ConfidenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate confidence score and route document",
    description=(
        "Calculates overall document confidence across classification, extraction, "
        "and validation stages. Determines approval recommendation (AUTO_APPROVE or REVIEW_REQUIRED) "
        "and updates document status."
    ),
    responses={
        200: {"description": "Confidence calculated and document routed."},
        404: {"description": "Document not found."},
        409: {"description": "Document has not completed validation."},
        422: {"description": "Confidence calculation failed."},
    },
)
async def calculate_confidence(
    document_id: uuid.UUID,
    db: DbSession,
) -> ConfidenceResponse:
    """Trigger confidence calculation and decision routing."""
    service = ConfidenceService(db=db)
    try:
        return await service.calculate_confidence(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValidationNotCompletedForConfidenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ConfidenceScoringError as exc:
        http_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        raise HTTPException(
            status_code=http_422,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "unhandled_confidence_endpoint_error",
            document_id=str(document_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while calculating confidence.",
        ) from exc


@router.get(
    "/{document_id}/confidence",
    response_model=ConfidenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve document confidence scoring result",
    description="Returns the calculated confidence scores, factors, and recommendation for a document.",
    responses={
        200: {"description": "Confidence score retrieved."},
        404: {"description": "Document not found."},
        409: {"description": "Document has not yet had confidence scored."},
    },
)
async def get_confidence(
    document_id: uuid.UUID,
    db: DbSession,
) -> ConfidenceResponse:
    """Get the confidence scoring outcome for a document."""
    service = ConfidenceService(db=db)
    try:
        return await service.get_confidence(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ConfidenceNotCalculatedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "unhandled_get_confidence_error",
            document_id=str(document_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving confidence score.",
        ) from exc
