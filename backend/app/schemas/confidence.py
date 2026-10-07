"""
schemas/confidence.py
=====================
Pydantic API schemas for confidence scoring and approval routing.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any
from pydantic import BaseModel, Field


class ConfidenceResponse(BaseModel):
    """API response schema for document confidence scoring."""

    document_id: uuid.UUID = Field(
        ...,
        description="Unique document identifier.",
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Combined overall confidence score (0.0 to 1.0).",
    )
    classification_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score from classification stage.",
    )
    extraction_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Completeness / confidence score from extraction stage.",
    )
    validation_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score from validation stage.",
    )
    recommendation: str = Field(
        ...,
        description="System decision recommendation: 'AUTO_APPROVE' or 'REVIEW_REQUIRED'.",
    )
    confidence_factors: dict[str, Any] = Field(
        default_factory=dict,
        description="Transparent breakdown of calculation weights and factor values.",
    )
    status: str = Field(
        ...,
        description="Updated document status ('APPROVED' or 'REVIEW_REQUIRED').",
    )
    calculated_at: datetime.datetime | None = Field(
        default=None,
        description="UTC timestamp when confidence scoring was calculated.",
    )
