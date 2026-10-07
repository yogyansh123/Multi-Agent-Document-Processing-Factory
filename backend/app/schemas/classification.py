"""
schemas/classification.py
==========================
Pydantic API schemas for document classification responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ClassificationResponse(BaseModel):
    """
    Response returned by classification endpoints:
    - POST /api/v1/documents/{document_id}/classify
    - GET  /api/v1/documents/{document_id}/classification
    """

    document_id: uuid.UUID = Field(description="Globally unique document identifier.")
    document_type: str = Field(description="Classified document type (e.g. 'INVOICE').")
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence score.")
    reasoning: str = Field(description="Model rationale for this classification.")
    signals: list[str] = Field(default_factory=list, description="Signals identified in the text.")
    status: str = Field(description="Current document status (e.g. 'CLASSIFIED').")
    classified_at: datetime | None = Field(default=None, description="UTC timestamp of classification.")

    model_config = {"from_attributes": True}
