"""
api/v1/endpoints/documents.py
==============================
Document resource route handlers.

Architecture:
- Handlers are thin: validate input → call service → return schema.
- No business logic in this module.
- Domain exceptions from DocumentService are caught and mapped to HTTP errors.
- SQLAlchemy models are never returned directly; always convert to schemas.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, UploadFile, status, Response

from app.api.deps import DbSession, Storage
from app.core.logging import get_logger
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentSummaryStatsResponse,
    DocumentWithHistoryResponse,
)
from app.schemas.processing_history import ProcessingHistoryResponse
from app.services.document import (
    DocumentNotFoundError,
    DocumentService,
    FileTooLargeError,
    StorageOperationError,
    UnsupportedFileTypeError,
)

router = APIRouter(tags=["Documents"])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _build_service(db: DbSession, storage: Storage) -> DocumentService:
    """Construct a DocumentService for the current request."""
    return DocumentService(db=db, storage=storage)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    description=(
        "Upload a document for processing. "
        "Supported types: PDF, PNG, JPG, JPEG, DOCX. "
        "Maximum file size is configurable via MAX_UPLOAD_SIZE_MB (default 25 MB)."
    ),
    operation_id="upload_document",
)
async def upload_document(
    file: UploadFile,
    db: DbSession,
    storage: Storage,
) -> DocumentResponse:
    """
    Upload a document and register it for processing.

    The file is validated (type and size), stored, and a database record
    is created with status UPLOADED.  An initial ProcessingHistory record
    is appended for the upload stage.
    """
    service = _build_service(db, storage)

    file_bytes = await file.read()
    original_filename = file.filename or "unknown"
    content_type = file.content_type or "application/octet-stream"

    logger.info(
        "document.upload.received",
        filename=original_filename,
        content_type=content_type,
        size_bytes=len(file_bytes),
    )

    try:
        document = await service.upload_document(
            file_bytes=file_bytes,
            original_filename=original_filename,
            content_type=content_type,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_REQUEST_ENTITY_TOO_LARGE", 413),
            detail=str(exc),
        ) from exc
    except StorageOperationError as exc:
        logger.error("document.upload.storage_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store the uploaded file. Please try again.",
        ) from exc

    return DocumentResponse.model_validate(document)


# ---------------------------------------------------------------------------
# Summary Stats
# ---------------------------------------------------------------------------


@router.get(
    "/stats/summary",
    response_model=DocumentSummaryStatsResponse,
    summary="Get document summary statistics",
    description="Return aggregated document statistics including status counts and average confidence.",
    operation_id="get_document_summary_stats",
)
async def get_document_summary_stats(
    db: DbSession,
    storage: Storage,
) -> DocumentSummaryStatsResponse:
    """Return aggregated document summary stats for the dashboard."""
    service = _build_service(db, storage)
    stats = await service.get_summary_stats()
    return DocumentSummaryStatsResponse.model_validate(stats)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
    description="Return a paginated list of documents with optional status, document_type, and filename search filters.",
    operation_id="list_documents",
)
async def list_documents(
    db: DbSession,
    storage: Storage,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(
        default=DocumentService.DEFAULT_PAGE_SIZE,
        ge=1,
        le=DocumentService.MAX_PAGE_SIZE,
        description=f"Items per page (max {DocumentService.MAX_PAGE_SIZE}).",
    ),
    status: str | None = Query(default=None, description="Optional document status filter."),
    document_type: str | None = Query(default=None, description="Optional document type filter."),
    search: str | None = Query(default=None, description="Optional filename search term."),
) -> DocumentListResponse:
    """Return a paginated list of documents ordered by upload date descending."""
    service = _build_service(db, storage)
    result = await service.list_documents(
        page=page,
        page_size=page_size,
        status=status,
        document_type=document_type,
        search=search,
    )

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(doc) for doc in result["items"]],
        page=result["page"],
        page_size=result["page_size"],
        total=result["total"],
        total_pages=result["total_pages"],
    )


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------


@router.get(
    "/{document_id}",
    response_model=DocumentWithHistoryResponse,
    summary="Get document by ID",
    description="Return a single document including its full processing history.",
    operation_id="get_document",
)
async def get_document(
    document_id: uuid.UUID,
    db: DbSession,
    storage: Storage,
) -> DocumentWithHistoryResponse:
    """Return a document and its processing history, or 404 if not found."""
    service = _build_service(db, storage)

    try:
        document = await service.get_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return DocumentWithHistoryResponse(
        **DocumentResponse.model_validate(document).model_dump(),
        processing_history=[
            ProcessingHistoryResponse.model_validate(h)
            for h in document.processing_history
        ],
    )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
    summary="Delete a document",
    description=(
        "Permanently delete a document and all associated data. "
        "Removes the stored file and all database records including processing history."
    ),
    operation_id="delete_document",
)
async def delete_document(
    document_id: uuid.UUID,
    db: DbSession,
    storage: Storage,
) -> None:
    """Delete a document and its physical file. Returns 204 No Content on success."""
    service = _build_service(db, storage)

    try:
        await service.delete_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except StorageOperationError as exc:
        logger.error(
            "document.delete.storage_error",
            document_id=str(document_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete the stored file. Please try again.",
        ) from exc
