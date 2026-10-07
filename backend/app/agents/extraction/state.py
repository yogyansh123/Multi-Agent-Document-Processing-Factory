"""
agents/extraction/state.py
==========================
Strongly typed state dictionary for the LangGraph Information Extraction Agent.
"""

from __future__ import annotations

from typing import Any, TypedDict


class ExtractionState(TypedDict, total=False):
    """
    State dictionary flowing through the Information Extraction Agent nodes.

    Fields:
    -------
    document_id:
        UUID string of the target document.
    document_text:
        Raw OCR extracted text of the document.
    document_type:
        Classified document category (INVOICE, RECEIPT, PURCHASE_ORDER, CONTRACT, OTHER).
    schema_name:
        Name of the Pydantic schema chosen for extraction.
    extracted_data:
        Structured extraction payload (dict representation of validated Pydantic model).
    extraction_version:
        Version string of prompt and schema applied (e.g. '1.0.0').
    error:
        Error message if validation, OCR retrieval, or extraction fails.
    """

    document_id: str
    document_text: str
    document_type: str
    schema_name: str | None
    extracted_data: dict[str, Any] | None
    extraction_version: str | None
    error: str | None
