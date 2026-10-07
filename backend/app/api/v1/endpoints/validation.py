"""
api/v1/endpoints/validation.py
==============================
FastAPI router for document validation endpoints.

Routes:
    POST /documents/{document_id}/validate   — Execute validation pipeline
    GET  /documents/{document_id}/validation — Retrieve validation results
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, Llm
from app.core.logging import get_logger
from app.schemas.validation import ValidationResponse
from app.services.validation_service import (
    ClassificationNotCompletedForValidationError,
    DocumentNotFoundError,
    DocumentNotValidatedError,
    ExtractionNotCompletedForValidationError,
    OcrNotCompletedForValidationError,
    ValidationError,
    ValidationService,
)

logger = get_logger("app.api.validation")

router = APIRouter()


@router.post(
    "/{document_id}/validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate extracted document data",
    description=(
        "Executes deterministic business rule validation and LLM semantic validation "
        "on extracted document data. Sets document status to VALIDATED."
    ),
    responses={
        200: {"description": "Document validated successfully."},
        404: {"description": "Document not found."},
        409: {"description": "Document has not completed OCR, classification, or extraction."},
        422: {"description": "Validation pipeline failed unrecoverably."},
    },
)
async def validate_document(
    document_id: uuid.UUID,
    db: DbSession,
    llm: Llm,
) -> ValidationResponse:
    """Trigger validation for an extracted document."""
    service = ValidationService(db=db, llm_provider=llm)
    try:
        return await service.validate_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        OcrNotCompletedForValidationError,
        ClassificationNotCompletedForValidationError,
        ExtractionNotCompletedForValidationError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValidationError as exc:
        http_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        raise HTTPException(
            status_code=http_422,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "unhandled_validation_endpoint_error",
            document_id=str(document_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while validating the document.",
        ) from exc


@router.get(
    "/{document_id}/validation",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve document validation results",
    description="Returns the latest validation result and issue list for a validated document.",
    responses={
        200: {"description": "Validation result retrieved."},
        404: {"description": "Document not found."},
        409: {"description": "Document has not yet been validated."},
    },
)
async def get_validation(
    document_id: uuid.UUID,
    db: DbSession,
) -> ValidationResponse:
    """Get the latest validation outcome for a document."""
    service = ValidationService(db=db)
    try:
        return await service.get_validation(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DocumentNotValidatedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "unhandled_get_validation_error",
            document_id=str(document_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving validation results.",
        ) from exc
