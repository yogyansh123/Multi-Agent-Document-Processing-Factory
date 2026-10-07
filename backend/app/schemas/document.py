"""
schemas/document.py
====================
Pydantic schemas for Document API responses.

These schemas are the ONLY way document data leaves the service layer.
SQLAlchemy model instances are never returned directly from endpoints.

Schemas deliberately omit:
- file_path (physical storage path — never exposed externally)
- stored_filename (internal implementation detail)
- error stack traces
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.processing_history import ProcessingHistoryResponse


class DocumentResponse(BaseModel):
    """
    API response for a single document.

    Omits physical storage path and stored filename for security.
    """

    id: uuid.UUID = Field(description="Globally unique document identifier.")
    original_filename: str = Field(description="Filename as provided by the uploader.")
    file_type: str = Field(description="Lowercase file extension (e.g. 'pdf', 'png').")
    mime_type: str = Field(description="MIME type of the uploaded file.")
    file_size: int = Field(description="File size in bytes.")
    document_type: str | None = Field(
        default=None,
        description=(
            "Detected document category (INVOICE, RECEIPT, PURCHASE_ORDER, "
            "CONTRACT, GENERAL). Null until classification completes."
        ),
    )
    status: str = Field(description="Current processing status.")
    error_message: str | None = Field(
        default=None,
        description="Error message if status is FAILED.",
    )
    ocr_provider: str | None = Field(
        default=None,
        description="OCR provider used (e.g. 'tesseract'). Null if OCR not yet performed.",
    )
    ocr_page_count: int | None = Field(
        default=None,
        description="Page/image count processed by OCR.",
    )
    ocr_processing_time_ms: int | None = Field(
        default=None,
        description="OCR processing time in milliseconds.",
    )
    ocr_completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp of OCR completion.",
    )
    ocr_metadata: dict | None = Field(
        default=None,
        description="Provider-specific OCR metadata.",
    )
    ocr_text: str | None = Field(default=None, description="Extracted OCR text.")
    classification_confidence: float | None = Field(default=None, description="Classification confidence score.")
    classification_reasoning: str | None = Field(default=None, description="Reasoning for classification.")
    classification_signals: list[str] | None = Field(default=None, description="Textual signals detected during classification.")
    classified_at: datetime | None = Field(default=None, description="UTC timestamp of classification.")
    extracted_data: dict | None = Field(default=None, description="Structured extracted document data.")
    extraction_version: str | None = Field(default=None, description="Schema/prompt version used for extraction.")
    extracted_at: datetime | None = Field(default=None, description="UTC timestamp of extraction.")
    validation_result: dict | None = Field(default=None, description="Validation issues and rules report.")
    validation_score: float | None = Field(default=None, description="Validation composite score (0.0 to 1.0).")
    validated_at: datetime | None = Field(default=None, description="UTC timestamp of validation.")
    overall_confidence: float | None = Field(default=None, description="Overall weighted confidence score.")
    extraction_confidence: float | None = Field(default=None, description="Extraction confidence component.")
    validation_confidence: float | None = Field(default=None, description="Validation confidence component.")
    confidence_recommendation: str | None = Field(default=None, description="AUTO_APPROVE or REVIEW_REQUIRED.")
    confidence_factors: dict | None = Field(default=None, description="Factor breakdown for confidence calculation.")
    confidence_calculated_at: datetime | None = Field(default=None, description="UTC timestamp of confidence calculation.")
    rag_indexed: bool = Field(default=False, description="Whether document is indexed in vector DB.")
    rag_indexed_at: datetime | None = Field(default=None, description="UTC timestamp of vector indexing.")
    rag_chunk_count: int | None = Field(default=None, description="Number of vector chunks generated.")
    rag_embedding_model: str | None = Field(default=None, description="Model used for vector embeddings.")
    created_at: datetime = Field(description="UTC timestamp when the document was uploaded.")
    updated_at: datetime = Field(description="UTC timestamp of the last status change.")

    model_config = {"from_attributes": True}


class DocumentSummaryStatsResponse(BaseModel):
    """Aggregate dashboard metrics for documents."""
    total_documents: int
    processing: int
    approved: int
    review_required: int
    rejected: int
    failed: int
    average_confidence: float | None = None
    rag_indexed_count: int = 0



class DocumentWithHistoryResponse(DocumentResponse):
    """
    Extended document response that includes full processing history.

    Returned by GET /api/v1/documents/{document_id}.
    """

    processing_history: list[ProcessingHistoryResponse] = Field(
        default_factory=list,
        description="Ordered list of processing stage records.",
    )


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    items: list[DocumentResponse] = Field(description="Documents on this page.")
    page: int = Field(ge=1, description="Current page number (1-indexed).")
    page_size: int = Field(ge=1, description="Number of items per page.")
    total: int = Field(ge=0, description="Total document count.")
    total_pages: int = Field(ge=0, description="Total number of pages.")

    model_config = {"from_attributes": True}
