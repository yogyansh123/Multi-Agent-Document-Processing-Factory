"""
api/v1/endpoints/classification.py
==================================
Document classification route handlers.

Routes:
- POST /api/v1/documents/{document_id}/classify
    Trigger the Classification Agent for an OCR-completed document.
- GET  /api/v1/documents/{document_id}/classification
    Retrieve latest classification result.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, Llm
from app.core.logging import get_logger
from app.schemas.classification import ClassificationResponse
from app.services.classification_service import (
    ClassificationError,
    ClassificationService,
    DocumentNotClassifiedError,
    OcrNotCompletedForClassificationError,
)
from app.services.document import DocumentNotFoundError
from app.services.llm.base import LLMConfigurationError, LLMError

router = APIRouter(tags=["Classification"])
logger = get_logger(__name__)


def _build_service(db: DbSession, llm: Llm) -> ClassificationService:
    return ClassificationService(db=db, llm=llm)


@router.post(
    "/{document_id}/classify",
    response_model=ClassificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Classify a document",
    description=(
        "Run the LangGraph Document Classification Agent on a document with completed OCR. "
        "Classifies document into INVOICE, RECEIPT, PURCHASE_ORDER, CONTRACT, or OTHER."
    ),
    responses={
        200: {"description": "Document classified successfully."},
        404: {"description": "Document not found."},
        409: {"description": "Document OCR has not completed."},
        422: {"description": "Classification failed or model refused."},
        500: {"description": "Internal server error."},
    },
)
async def classify_document(
    document_id: uuid.UUID,
    db: DbSession,
    llm: Llm,
) -> ClassificationResponse:
    """
    Trigger AI document classification via LangGraph.
    """
    service = _build_service(db, llm)

    try:
        doc = await service.classify_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except OcrNotCompletedForClassificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (ClassificationError, LLMError) as exc:
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "classification.unhandled_error",
            document_id=str(document_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during classification.",
        ) from exc

    return ClassificationResponse(
        document_id=doc.id,
        document_type=doc.document_type or "OTHER",
        confidence=doc.classification_confidence or 0.0,
        reasoning=doc.classification_reasoning or "",
        signals=doc.classification_signals or [],
        status=doc.status,
        classified_at=doc.classified_at,  # type: ignore[arg-type]
    )


@router.get(
    "/{document_id}/classification",
    response_model=ClassificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document classification",
    description="Retrieve the latest classification result for a classified document.",
    responses={
        200: {"description": "Classification retrieved successfully."},
        404: {"description": "Document not found."},
        409: {"description": "Document has not yet been classified."},
    },
)
async def get_classification(
    document_id: uuid.UUID,
    db: DbSession,
    llm: Llm,
) -> ClassificationResponse:
    """
    Fetch existing classification details for a document.
    """
    service = _build_service(db, llm)

    try:
        doc = await service.get_classification(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DocumentNotClassifiedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ClassificationResponse(
        document_id=doc.id,
        document_type=doc.document_type or "OTHER",
        confidence=doc.classification_confidence or 0.0,
        reasoning=doc.classification_reasoning or "",
        signals=doc.classification_signals or [],
        status=doc.status,
        classified_at=doc.classified_at,  # type: ignore[arg-type]
    )
