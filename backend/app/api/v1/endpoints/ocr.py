"""
api/v1/endpoints/ocr.py
=======================
OCR execution and extracted text retrieval endpoints.

Routes:
- POST /api/v1/documents/{document_id}/ocr
    Triggers OCR extraction for the document.
- GET  /api/v1/documents/{document_id}/text
    Returns the full extracted text for a document that has completed OCR.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, Ocr, Storage
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.ocr import OcrResultResponse, OcrTextResponse
from app.services.document import DocumentNotFoundError
from app.services.ocr.base import OCRError
from app.services.ocr_service import OcrNotCompletedError, OcrService

router = APIRouter(tags=["OCR"])
logger = get_logger(__name__)


def _build_ocr_service(db: DbSession, storage: Storage, ocr: Ocr) -> OcrService:
    return OcrService(db=db, storage=storage, ocr=ocr)


@router.post(
    "/{document_id}/ocr",
    response_model=OcrResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger OCR extraction",
    description=(
        "Run OCR on an uploaded document using the configured OCR provider. "
        "Extracts text, updates document status to OCR_COMPLETED (or FAILED on error), "
        "and logs the execution in processing history."
    ),
    responses={
        200: {"description": "OCR completed successfully."},
        404: {"description": "Document not found."},
        422: {"description": "OCR processing failed or unprocessable document."},
        500: {"description": "Internal server error."},
    },
)
async def trigger_ocr(
    document_id: uuid.UUID,
    db: DbSession,
    storage: Storage,
    ocr: Ocr,
) -> OcrResultResponse:
    """
    Trigger OCR text extraction for a document.
    """
    service = _build_ocr_service(db, storage, ocr)

    try:
        doc = await service.run_ocr(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except OCRError as exc:
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("ocr.unhandled_error", document_id=str(document_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during OCR processing.",
        ) from exc

    preview_chars = settings.OCR_TEXT_PREVIEW_CHARS
    full_text = doc.ocr_text or ""
    preview = full_text[:preview_chars]

    return OcrResultResponse(
        document_id=doc.id,
        status=doc.status,
        ocr_provider=doc.ocr_provider or ocr.provider_name,
        page_count=doc.ocr_page_count or 1,
        processing_time_ms=doc.ocr_processing_time_ms or 0,
        text_preview=preview,
        ocr_completed_at=doc.ocr_completed_at,  # type: ignore[arg-type]
        metadata=doc.ocr_metadata or {},
    )


@router.get(
    "/{document_id}/text",
    response_model=OcrTextResponse,
    status_code=status.HTTP_200_OK,
    summary="Get full extracted OCR text",
    description="Retrieve the complete extracted text for a document that has completed OCR.",
    responses={
        200: {"description": "Extracted text retrieved successfully."},
        404: {"description": "Document not found."},
        409: {"description": "Document has not yet completed OCR."},
    },
)
async def get_document_text(
    document_id: uuid.UUID,
    db: DbSession,
    storage: Storage,
    ocr: Ocr,
) -> OcrTextResponse:
    """
    Retrieve full OCR extracted text for a document.
    """
    service = _build_ocr_service(db, storage, ocr)

    try:
        doc = await service.get_document_text(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except OcrNotCompletedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return OcrTextResponse(
        document_id=doc.id,
        status=doc.status,
        ocr_provider=doc.ocr_provider,
        text=doc.ocr_text or "",
    )
