"""
activities/schemas.py
=====================
Pydantic schemas for Temporal activity and workflow inputs and outputs.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class DocumentActivityInput(BaseModel):
    """Input payload passed to document processing activities."""

    document_id: str = Field(
        ...,
        description="String UUID of the document to process.",
    )


class DocumentActivityResult(BaseModel):
    """Result returned by each document processing activity."""

    document_id: str = Field(
        ...,
        description="String UUID of the processed document.",
    )
    stage: str = Field(
        ...,
        description="Processing stage name (e.g. 'OCR', 'CLASSIFICATION').",
    )
    status: str = Field(
        ...,
        description="Stage completion status ('COMPLETED' or 'FAILED').",
    )
    message: str = Field(
        default="",
        description="Summary message about stage execution.",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Key output data from the stage.",
    )


class DocumentWorkflowResult(BaseModel):
    """Final result produced by DocumentProcessingWorkflow."""

    document_id: str = Field(
        ...,
        description="String UUID of the document.",
    )
    status: str = Field(
        ...,
        description="Final document processing status ('APPROVED', 'REVIEW_REQUIRED', or 'FAILED').",
    )
    document_type: str | None = Field(
        default=None,
        description="Classified document category.",
    )
    overall_confidence: float | None = Field(
        default=None,
        description="Calculated overall confidence score.",
    )
    recommendation: str | None = Field(
        default=None,
        description="Approval recommendation ('AUTO_APPROVE' or 'REVIEW_REQUIRED').",
    )
    stages_completed: list[str] = Field(
        default_factory=list,
        description="List of stages completed during workflow execution.",
    )
