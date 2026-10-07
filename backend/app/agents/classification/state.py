"""
agents/classification/state.py
==============================
Strongly typed state representation for the Classification Agent LangGraph workflow.
"""

from __future__ import annotations

from typing import TypedDict


class ClassificationState(TypedDict, total=False):
    """
    State dictionary flowing through the Classification Agent nodes.

    Fields:
    -------
    document_id:
        UUID string of the target document.
    document_text:
        Raw OCR extracted text of the document.
    document_type:
        Identified document category (INVOICE, RECEIPT, PURCHASE_ORDER, CONTRACT, OTHER).
    confidence:
        Confidence score between 0.0 and 1.0.
    reasoning:
        Explanation of classification decision.
    signals:
        List of identified features and tokens supporting the classification.
    error:
        Error message if validation, OCR retrieval, or classification fails.
    """

    document_id: str
    document_text: str
    document_type: str | None
    confidence: float | None
    reasoning: str | None
    signals: list[str] | None
    error: str | None
