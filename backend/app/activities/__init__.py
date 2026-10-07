"""
activities/__init__.py
======================
Temporal activity implementations for the Multi-Agent Document Processing Factory.

Exports all activity functions and their typed schemas.
"""

from __future__ import annotations

from app.activities.document_activities import (
    classify_document_activity,
    extract_fields_activity,
    run_ocr_activity,
    score_confidence_activity,
    validate_document_activity,
)
from app.activities.schemas import (
    DocumentActivityInput,
    DocumentActivityResult,
    DocumentWorkflowResult,
)

__all__ = [
    "run_ocr_activity",
    "classify_document_activity",
    "extract_fields_activity",
    "validate_document_activity",
    "score_confidence_activity",
    "DocumentActivityInput",
    "DocumentActivityResult",
    "DocumentWorkflowResult",
]
