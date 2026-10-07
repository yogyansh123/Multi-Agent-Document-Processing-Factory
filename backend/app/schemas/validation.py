"""
schemas/validation.py
=====================
Pydantic API schemas for document validation endpoints.
"""

from __future__ import annotations

import datetime
import uuid
from pydantic import BaseModel, Field

from app.agents.validation.schemas import ValidationIssue


class ValidationResponse(BaseModel):
    """API response schema for document validation."""

    document_id: uuid.UUID = Field(
        ...,
        description="Unique document identifier.",
    )
    document_type: str | None = Field(
        default=None,
        description="Classified document category.",
    )
    is_valid: bool = Field(
        ...,
        description="Whether the document passed validation without ERROR severity issues.",
    )
    validation_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Composite validation score (0.0 to 1.0).",
    )
    issues: list[ValidationIssue] = Field(
        default_factory=list,
        description="List of detected validation issues.",
    )
    rules_checked: list[str] = Field(
        default_factory=list,
        description="List of rules evaluated.",
    )
    status: str = Field(
        ...,
        description="Current document status (e.g. 'VALIDATED').",
    )
    validated_at: datetime.datetime | None = Field(
        default=None,
        description="UTC timestamp when validation was completed.",
    )
