"""
schemas/processing_history.py
==============================
Pydantic schemas for ProcessingHistory API responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProcessingHistoryResponse(BaseModel):
    """
    API response schema for a single ProcessingHistory record.

    Note: error_details is deliberately omitted from the public response
    to avoid exposing internal implementation details.
    Only the sanitised `message` field is returned.
    """

    id: uuid.UUID = Field(description="Unique ID of this history record.")
    document_id: uuid.UUID = Field(description="ID of the parent document.")
    stage: str = Field(description="Processing stage name.")
    status: str = Field(description="Status of this stage attempt.")
    message: str | None = Field(default=None, description="Human-readable stage message.")
    started_at: datetime | None = Field(default=None, description="UTC start time of this stage.")
    completed_at: datetime | None = Field(default=None, description="UTC completion time of this stage.")
    created_at: datetime = Field(description="UTC timestamp when this record was created.")

    model_config = {"from_attributes": True}
