"""
schemas/extraction.py
=====================
Pydantic API schemas for document extraction responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExtractionResponse(BaseModel):
    """
    Response returned by information extraction endpoints:
    - POST /api/v1/documents/{document_id}/extract
    - GET  /api/v1/documents/{document_id}/extraction
    """

    document_id: uuid.UUID = Field(description="Globally unique document identifier.")
    document_type: str = Field(description="Classified document type (e.g. 'INVOICE').")
    extraction_version: str = Field(description="Version of the extraction prompt and schema.")
    extracted_data: dict[str, Any] = Field(description="Structured extracted data payload.")
    status: str = Field(description="Current document status (e.g. 'EXTRACTED').")
    extracted_at: datetime | None = Field(default=None, description="UTC timestamp of extraction completion.")

    model_config = {"from_attributes": True}
