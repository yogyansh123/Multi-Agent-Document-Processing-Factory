"""
agents/validation/nodes.py
==========================
LangGraph node implementations for the Document Validation Agent.

Nodes:
- load_document: Retrieves document record and verifies prior stages.
- load_extraction: Confirms extracted data exists.
- run_deterministic_validation: Executes business rules (arithmetic, dates, fields).
- run_semantic_validation: Calls LLMProvider for contextual consistency review.
- combine_validation_results: Merges issues, calculates composite score and is_valid flag.
- persist_validation: Updates document model and sets status=VALIDATED.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.validation.prompts import (
    SEMANTIC_VALIDATION_SYSTEM_PROMPT,
    build_semantic_validation_prompt,
)
from app.agents.validation.rules import validate_deterministic
from app.agents.validation.schemas import (
    SemanticValidationResult,
    ValidationIssue,
    ValidationResult,
)
from app.agents.validation.state import ValidationState
from app.core.enums import DocumentStatus, ValidationSeverity
from app.core.logging import get_logger
from app.models.document import Document
from app.services.llm.base import LLMProvider

logger = get_logger("app.agents.validation")


async def load_document(
    state: ValidationState,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """Retrieve document from DB if text, type, or extraction are not pre-populated."""
    if state.get("error"):
        return {}

    # If state is already fully loaded (e.g. in unit tests)
    if (
        state.get("document_text")
        and state.get("document_type")
        and state.get("extracted_data") is not None
    ):
        return {}

    doc_id_str = state.get("document_id")
    if not doc_id_str or not db:
        return {"error": "Missing document_id or database session"}

    try:
        doc_uuid = uuid.UUID(doc_id_str)
    except ValueError:
        return {"error": f"Invalid document UUID: {doc_id_str}"}

    result = await db.execute(select(Document).where(Document.id == doc_uuid))
    document = result.scalar_one_or_none()

    if not document:
        return {"error": f"Document not found: {doc_id_str}"}

    if not document.ocr_text:
        return {"error": f"Document {doc_id_str} has not completed OCR"}

    if not document.document_type:
        return {"error": f"Document {doc_id_str} has not completed classification"}

    if document.extracted_data is None:
        return {"error": f"Document {doc_id_str} has not completed information extraction"}

    return {
        "document_text": document.ocr_text,
        "document_type": document.document_type,
        "extracted_data": document.extracted_data,
    }


def load_extraction(state: ValidationState) -> dict[str, Any]:
    """Verify that extracted data is present and valid."""
    if state.get("error"):
        return {}

    extracted_data = state.get("extracted_data")
    if extracted_data is None:
        return {"error": "No extracted data found for validation."}

    if not isinstance(extracted_data, dict):
        return {"error": "Extracted data is not a valid dictionary."}

    return {}


def run_deterministic_validation(state: ValidationState) -> dict[str, Any]:
    """Execute deterministic arithmetic, date, and field presence rules."""
    if state.get("error"):
        return {}

    doc_type = state.get("document_type", "OTHER")
    extracted_data = state.get("extracted_data", {})

    issues, rules_checked = validate_deterministic(doc_type, extracted_data)

    return {
        "deterministic_issues": [issue.model_dump() for issue in issues],
        "rules_checked": rules_checked,
    }


async def run_semantic_validation(
    state: ValidationState,
    llm_provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Execute LLM-assisted semantic validation against OCR text."""
    if state.get("error"):
        return {}

    if not llm_provider:
        # Graceful fallback if no LLM provider is provided (e.g. deterministic-only run)
        return {"semantic_issues": [], "semantic_score": 1.0}

    doc_text = state.get("document_text", "")
    doc_type = state.get("document_type", "OTHER")
    extracted_data = state.get("extracted_data", {})

    prompt = build_semantic_validation_prompt(doc_text, doc_type, extracted_data)

    try:
        result: SemanticValidationResult = await llm_provider.generate_structured(
            prompt=prompt,
            schema=SemanticValidationResult,
            system_prompt=SEMANTIC_VALIDATION_SYSTEM_PROMPT,
            temperature=0.0,
        )

        semantic_issues = [
            ValidationIssue(
                code=issue.code,
                field=issue.field,
                message=issue.message,
                severity=issue.severity,
                actual_value=issue.actual_value,
                expected_value=issue.expected_value,
            ).model_dump()
            for issue in result.issues
        ]

        rules = list(state.get("rules_checked", []))
        rules.append("SEMANTIC_COHERENCE_CHECK")

        return {
            "semantic_issues": semantic_issues,
            "semantic_score": max(0.0, min(1.0, float(result.semantic_score))),
            "rules_checked": rules,
        }
    except Exception as exc:
        logger.warning(
            "semantic_validation_warning",
            error=str(exc),
            document_id=state.get("document_id"),
        )
        # LLM failure during validation does not crash the pipeline; fallback to neutral score
        return {
            "semantic_issues": [
                ValidationIssue(
                    code="SEMANTIC_VALIDATION_SKIPPED",
                    field="general",
                    message=f"Semantic validation could not complete: {exc}",
                    severity=ValidationSeverity.INFO,
                ).model_dump()
            ],
            "semantic_score": 1.0,
        }


def combine_validation_results(state: ValidationState) -> dict[str, Any]:
    """
    Merge deterministic and semantic validation issues, compute composite validation score,
    and determine validity (is_valid is True if no ERROR severity issues exist).
    """
    if state.get("error"):
        return {}

    deterministic_issues_raw = state.get("deterministic_issues", [])
    semantic_issues_raw = state.get("semantic_issues", [])
    rules_checked = state.get("rules_checked", [])

    all_issues_raw = deterministic_issues_raw + semantic_issues_raw
    issues: list[ValidationIssue] = [
        ValidationIssue(**iss) for iss in all_issues_raw
    ]

    # Calculate deterministic penalty score
    error_count = sum(1 for iss in issues if iss.severity == ValidationSeverity.ERROR)
    warning_count = sum(1 for iss in issues if iss.severity == ValidationSeverity.WARNING)
    info_count = sum(1 for iss in issues if iss.severity == ValidationSeverity.INFO)

    penalty = (error_count * 0.25) + (warning_count * 0.08) + (info_count * 0.02)
    deterministic_score = max(0.0, min(1.0, round(1.0 - penalty, 4)))

    # Semantic component
    semantic_score = state.get("semantic_score", 1.0)

    # Composite validation score (70% deterministic, 30% semantic)
    composite_score = round((0.70 * deterministic_score) + (0.30 * semantic_score), 4)
    composite_score = max(0.0, min(1.0, composite_score))

    is_valid = error_count == 0

    val_result = ValidationResult(
        is_valid=is_valid,
        issues=issues,
        rules_checked=rules_checked,
        validation_score=composite_score,
    )

    return {
        "validation_result": val_result.model_dump(),
        "validation_score": composite_score,
        "is_valid": is_valid,
    }


async def persist_validation(
    state: ValidationState,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """Persist validation outcome to the database and update document status."""
    if state.get("error") or not db:
        return {}

    doc_id_str = state.get("document_id")
    if not doc_id_str:
        return {}

    try:
        doc_uuid = uuid.UUID(doc_id_str)
        result = await db.execute(select(Document).where(Document.id == doc_uuid))
        document = result.scalar_one_or_none()

        if document:
            document.validation_result = state.get("validation_result")
            document.validation_score = state.get("validation_score")
            document.validated_at = datetime.datetime.now(datetime.timezone.utc)
            document.status = DocumentStatus.VALIDATED.value
            await db.commit()
    except Exception as exc:
        logger.error("persist_validation_error", error=str(exc))
        return {"error": f"Failed to persist validation: {exc}"}

    return {}
