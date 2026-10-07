"""
schemas/review.py
=================
Pydantic schemas for the Human-in-the-Loop review system.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.processing_history import ProcessingHistoryResponse


class ReviewQueueItem(BaseModel):
    """Single item in the review queue."""
    model_config = ConfigDict(from_attributes=True)

    review_id: uuid.UUID
    document_id: uuid.UUID
    original_filename: str
    document_type: str | None = None
    status: str
    overall_confidence: float | None = None
    confidence_recommendation: str | None = None
    validation_score: float | None = None
    created_at: datetime


class ReviewQueueResponse(BaseModel):
    """Paginated list of review queue items."""
    items: list[ReviewQueueItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReviewDocumentDetails(BaseModel):
    """Document snapshot embedded in review details."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    file_type: str
    mime_type: str
    file_size: int
    document_type: str | None = None
    status: str
    ocr_text: str | None = None
    classification_confidence: float | None = None
    classification_reasoning: str | None = None
    extracted_data: dict[str, Any] | None = None
    validation_score: float | None = None
    validation_result: dict[str, Any] | None = None
    overall_confidence: float | None = None
    confidence_recommendation: str | None = None
    confidence_factors: dict[str, Any] | None = None
    rag_indexed: bool = Field(default=False, description="Whether document is indexed in vector DB.")
    rag_indexed_at: datetime | None = Field(default=None, description="UTC timestamp of vector indexing.")
    rag_chunk_count: int | None = Field(default=None, description="Number of vector chunks generated.")
    rag_embedding_model: str | None = Field(default=None, description="Model used for vector embeddings.")


class ReviewDetailsResponse(BaseModel):
    """Comprehensive details for a single document review."""
    model_config = ConfigDict(from_attributes=True)

    review_id: uuid.UUID
    document_id: uuid.UUID
    status: str
    reviewer_id: str | None = None
    reviewer_name: str | None = None
    decision: str | None = None
    reason: str | None = None
    original_extracted_data: dict[str, Any] | None = None
    reviewed_extracted_data: dict[str, Any] | None = None
    validation_result_snapshot: dict[str, Any] | None = None
    confidence_snapshot: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None
    document: ReviewDocumentDetails
    history: list[ProcessingHistoryResponse] = Field(default_factory=list)


class ReviewDecisionRequest(BaseModel):
    """Request payload for approving or rejecting a review."""
    reason: str | None = Field(default=None, description="Optional decision rationale.")
    reviewer_name: str | None = Field(default=None, description="Optional reviewer name.")


class CorrectionRequest(BaseModel):
    """Request payload for correcting structured extraction."""
    corrected_data: dict[str, Any] = Field(..., description="Corrected structured data conforming to document schema.")
    reason: str | None = Field(default=None, description="Optional explanation of modifications.")
    reviewer_name: str | None = Field(default=None, description="Optional reviewer name.")


class ReviewActionResponse(BaseModel):
    """Response returned upon performing a review lifecycle action."""
    model_config = ConfigDict(from_attributes=True)

    review_id: uuid.UUID
    document_id: uuid.UUID
    status: str
    decision: str | None = None
    reason: str | None = None
    reviewed_at: datetime | None = None
    document_status: str
    message: str
    validation_score: float | None = None
    overall_confidence: float | None = None
