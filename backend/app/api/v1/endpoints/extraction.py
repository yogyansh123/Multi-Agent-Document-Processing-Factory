"""
api/v1/endpoints/extraction.py
==============================
Information extraction route handlers.

Routes:
- POST /api/v1/documents/{document_id}/extract
    Trigger the Information Extraction Agent for a classified document.
- GET  /api/v1/documents/{document_id}/extraction
    Retrieve latest structured extraction data.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, Llm
from app.core.logging import get_logger
from app.schemas.extraction import ExtractionResponse
from app.services.document import DocumentNotFoundError
from app.services.extraction_service import (
    ClassificationNotCompletedForExtractionError,
    DocumentNotExtractedError,
    ExtractionError,
    ExtractionService,
    OcrNotCompletedForExtractionError,
)
from app.services.llm.base import LLMConfigurationError, LLMError

router = APIRouter(tags=["Extraction"])
logger = get_logger(__name__)


def _build_service(db: DbSession, llm: Llm) -> ExtractionService:
    return ExtractionService(db=db, llm=llm)


@router.post(
    "/{document_id}/extract",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract document information",
    description=(
        "Run the LangGraph Information Extraction Agent on a classified document. "
        "Extracts structured data adhering to the document-type-specific schema."
    ),
    responses={
        200: {"description": "Information extracted successfully."},
        404: {"description": "Document not found."},
        409: {"description": "Prerequisite not met (OCR or Classification incomplete)."},
        422: {"description": "Extraction failed or structured output invalid."},
        500: {"description": "Internal server error."},
    },
)
async def extract_document(
    document_id: uuid.UUID,
    db: DbSession,
    llm: Llm,
) -> ExtractionResponse:
    """
    Trigger structured information extraction via LangGraph.
    """
    service = _build_service(db, llm)

    try:
        doc = await service.extract_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (OcrNotCompletedForExtractionError, ClassificationNotCompletedForExtractionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (ExtractionError, LLMError) as exc:
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "extraction.unhandled_error",
            document_id=str(document_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during information extraction.",
        ) from exc

    return ExtractionResponse(
        document_id=doc.id,
        document_type=doc.document_type or "OTHER",
        extraction_version=doc.extraction_version or "1.0.0",
        extracted_data=doc.extracted_data or {},
        status=doc.status,
        extracted_at=doc.extracted_at,  # type: ignore[arg-type]
    )


@router.get(
    "/{document_id}/extraction",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get extracted information",
    description="Retrieve the latest structured extraction result for an extracted document.",
    responses={
        200: {"description": "Extracted data retrieved successfully."},
        404: {"description": "Document not found."},
        409: {"description": "Document has not yet completed information extraction."},
    },
)
async def get_extraction(
    document_id: uuid.UUID,
    db: DbSession,
    llm: Llm,
) -> ExtractionResponse:
    """
    Fetch existing structured extraction details for a document.
    """
    service = _build_service(db, llm)

    try:
        doc = await service.get_extraction(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DocumentNotExtractedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ExtractionResponse(
        document_id=doc.id,
        document_type=doc.document_type or "OTHER",
        extraction_version=doc.extraction_version or "1.0.0",
        extracted_data=doc.extracted_data or {},
        status=doc.status,
        extracted_at=doc.extracted_at,  # type: ignore[arg-type]
    )
