"""
schemas/workflow.py
===================
Pydantic API schemas for Temporal workflow execution and status query.
"""

from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


class StartWorkflowResponse(BaseModel):
    """Response returned when initiating an asynchronous processing workflow."""

    document_id: uuid.UUID = Field(
        ...,
        description="Unique document identifier.",
    )
    workflow_id: str = Field(
        ...,
        description="Temporal workflow identifier.",
    )
    run_id: str = Field(
        ...,
        description="Temporal execution run identifier.",
    )
    status: str = Field(
        ...,
        description="Current document status (e.g. 'PROCESSING').",
    )
    message: str = Field(
        default="Document processing workflow initiated.",
        description="Informational status message.",
    )


class WorkflowStatusResponse(BaseModel):
    """Response returned when querying an active or completed workflow."""

    document_id: uuid.UUID = Field(
        ...,
        description="Unique document identifier.",
    )
    workflow_id: str = Field(
        ...,
        description="Temporal workflow identifier.",
    )
    run_id: str | None = Field(
        default=None,
        description="Temporal execution run identifier.",
    )
    workflow_status: str = Field(
        ...,
        description="Temporal workflow state (e.g. 'RUNNING', 'COMPLETED').",
    )
    current_stage: str = Field(
        ...,
        description="Current pipeline stage being processed.",
    )
    document_status: str = Field(
        ...,
        description="Database document status.",
    )
