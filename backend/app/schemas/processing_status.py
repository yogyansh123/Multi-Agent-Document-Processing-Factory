"""
schemas/processing_status.py
============================
Pydantic schemas for the document processing status endpoint.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProcessingStatusResponse(BaseModel):
    """
    Consolidated processing status representation.
    """
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    status: str
    current_stage: str | None = None
    workflow_id: str | None = None
    overall_confidence: float | None = None
    confidence_recommendation: str | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    failed_stage: str | None = None
    error_message: str | None = None
    review_id: str | None = None
    review_status: str | None = None

