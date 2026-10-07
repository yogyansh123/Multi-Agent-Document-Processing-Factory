"""
schemas/ocr.py
==============
Pydantic schemas for OCR API request/responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OcrResultResponse(BaseModel):
    """
    Response returned after triggering OCR processing on a document.
    """

    document_id: uuid.UUID = Field(description="Unique identifier of the processed document.")
    status: str = Field(description="Document processing status after OCR.")
    ocr_provider: str = Field(description="OCR engine used (e.g. 'tesseract').")
    page_count: int = Field(description="Number of pages/images processed.")
    processing_time_ms: int = Field(description="Wall-clock OCR processing time in milliseconds.")
    text_preview: str = Field(description="Truncated preview of the extracted text.")
    ocr_completed_at: datetime = Field(description="UTC timestamp when OCR completed.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific supplementary metadata.",
    )

    model_config = {"from_attributes": True}


class OcrTextResponse(BaseModel):
    """
    Full text payload returned by GET /api/v1/documents/{document_id}/text.
    """

    document_id: uuid.UUID = Field(description="Document identifier.")
    status: str = Field(description="Current document status.")
    ocr_provider: str | None = Field(default=None, description="OCR provider name.")
    text: str = Field(description="Complete extracted text.")

    model_config = {"from_attributes": True}
