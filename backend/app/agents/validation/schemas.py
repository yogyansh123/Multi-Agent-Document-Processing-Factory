"""
agents/validation/schemas.py
============================
Strongly typed Pydantic models for the validation system.

Defines schemas for:
- Validation issues with severity (INFO, WARNING, ERROR)
- Deterministic and semantic validation results
- Combined validation output
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.core.enums import ValidationSeverity


class ValidationIssue(BaseModel):
    """
    A single issue identified during deterministic or semantic validation.
    """

    code: str = Field(
        ...,
        description="Machine-readable issue code (e.g. 'ARITHMETIC_MISMATCH', 'MISSING_REQUIRED_FIELD').",
    )
    field: str = Field(
        ...,
        description="Name or path of the field associated with the issue (e.g. 'line_items[0].total_amount').",
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of the validation issue.",
    )
    severity: ValidationSeverity = Field(
        ...,
        description="Severity level: INFO, WARNING, or ERROR.",
    )
    actual_value: Any = Field(
        default=None,
        description="The actual value extracted from the document, if applicable.",
    )
    expected_value: Any = Field(
        default=None,
        description="The expected value or range, if applicable.",
    )


class ValidationResult(BaseModel):
    """
    Combined validation outcome for a document.
    """

    is_valid: bool = Field(
        ...,
        description="True if no ERROR severity issues were encountered.",
    )
    issues: list[ValidationIssue] = Field(
        default_factory=list,
        description="List of all validation issues identified (INFO, WARNING, ERROR).",
    )
    rules_checked: list[str] = Field(
        default_factory=list,
        description="Identifiers of all deterministic and semantic rules evaluated.",
    )
    validation_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Composite validation score between 0.0 and 1.0.",
    )


class SemanticValidationIssue(BaseModel):
    """
    An issue identified by the LLM semantic validation step.
    """

    code: str = Field(
        ...,
        description="Semantic issue code (e.g. 'SEMANTIC_ANOMALY', 'CONTRADICTORY_DATA').",
    )
    field: str = Field(
        ...,
        description="Field or section where semantic inconsistency was detected.",
    )
    message: str = Field(
        ...,
        description="Clear explanation of the semantic issue.",
    )
    severity: ValidationSeverity = Field(
        default=ValidationSeverity.WARNING,
        description="Severity of the semantic issue.",
    )
    actual_value: str | None = Field(
        default=None,
        description="Extracted text or value that appears anomalous.",
    )
    expected_value: str | None = Field(
        default=None,
        description="What would be expected in standard business context.",
    )


class SemanticValidationResult(BaseModel):
    """
    Structured response schema returned by the LLM semantic validation prompt.
    """

    issues: list[SemanticValidationIssue] = Field(
        default_factory=list,
        description="List of semantic anomalies detected.",
    )
    semantic_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Semantic coherence score (0.0 to 1.0).",
    )
    summary: str = Field(
        default="",
        description="Concise summary of semantic validation findings.",
    )
