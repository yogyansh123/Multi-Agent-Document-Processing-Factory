"""
schemas/analytics.py
====================
Pydantic schemas for analytics and observability endpoints.

Covers:
- High-level KPI summary
- Document status distribution
- Document type distribution
- Confidence metrics
- Stage performance & duration
- Human review workload statistics
- Time-series processing volume
- Recent system activity events
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class AnalyticsSummary(BaseModel):
    """Overall summary KPIs calculated from active documents and workflow runs."""

    total_documents: int = Field(ge=0, description="Total number of documents uploaded.")
    approved_documents: int = Field(ge=0, description="Number of approved documents.")
    rejected_documents: int = Field(ge=0, description="Number of rejected documents.")
    processing_documents: int = Field(ge=0, description="Number of documents currently processing.")
    review_required_documents: int = Field(ge=0, description="Number of documents awaiting human review.")
    failed_documents: int = Field(ge=0, description="Number of documents that failed processing.")
    average_confidence: float | None = Field(
        default=None,
        description="Average overall confidence score (0.0 to 1.0) across scored documents.",
    )
    average_processing_time_ms: float | None = Field(
        default=None,
        description="Average processing time in milliseconds for completed documents.",
    )
    rag_indexed_documents: int = Field(ge=0, description="Number of documents indexed into vector DB.")
    auto_approved_documents: int = Field(ge=0, description="Number of documents auto-approved without human review.")
    human_reviewed_documents: int = Field(ge=0, description="Number of documents that went through human review.")

    model_config = {"from_attributes": True}


class StatusDistributionItem(BaseModel):
    """Breakdown of document counts and percentages by DocumentStatus."""

    status: str = Field(description="Document status enum value.")
    count: int = Field(ge=0, description="Number of documents with this status.")
    percentage: float = Field(ge=0.0, le=100.0, description="Percentage of total documents.")


class StatusDistributionResponse(BaseModel):
    """Response containing status distribution items and total count."""

    items: list[StatusDistributionItem] = Field(description="List of status counts and percentages.")
    total: int = Field(ge=0, description="Total documents counted.")


class DocumentTypeDistributionItem(BaseModel):
    """Breakdown of document counts and percentages by DocumentType."""

    document_type: str = Field(description="Document type classification name (e.g. INVOICE, RECEIPT).")
    count: int = Field(ge=0, description="Number of documents with this type.")
    percentage: float = Field(ge=0.0, le=100.0, description="Percentage of classified documents.")


class DocumentTypeDistributionResponse(BaseModel):
    """Response containing document type distribution items and total classified count."""

    items: list[DocumentTypeDistributionItem] = Field(description="List of document type counts and percentages.")
    total: int = Field(ge=0, description="Total classified documents.")


class ConfidenceStatistics(BaseModel):
    """Aggregate confidence statistics across all scored documents."""

    average_overall: float | None = Field(default=None, description="Average overall confidence score.")
    average_classification: float | None = Field(default=None, description="Average classification confidence.")
    average_extraction: float | None = Field(default=None, description="Average extraction confidence.")
    average_validation: float | None = Field(default=None, description="Average validation confidence.")
    min_confidence: float | None = Field(default=None, description="Minimum confidence recorded.")
    max_confidence: float | None = Field(default=None, description="Maximum confidence recorded.")
    auto_approve_count: int = Field(ge=0, description="Documents recommended for AUTO_APPROVE.")
    review_required_count: int = Field(ge=0, description="Documents recommended for REVIEW_REQUIRED.")


class StagePerformanceItem(BaseModel):
    """Aggregated performance metrics for a single processing stage."""

    stage: str = Field(description="Processing stage name (e.g. OCR, CLASSIFICATION, EXTRACTION).")
    executions: int = Field(ge=0, description="Total number of execution attempts for this stage.")
    completed: int = Field(ge=0, description="Number of successful completions.")
    failed: int = Field(ge=0, description="Number of failed attempts.")
    average_duration_ms: float | None = Field(
        default=None,
        description="Average execution duration in milliseconds.",
    )
    success_rate: float = Field(
        ge=0.0,
        le=100.0,
        description="Percentage of executions that succeeded (0.0 to 100.0).",
    )


class StagePerformanceResponse(BaseModel):
    """Response containing performance metrics across all pipeline stages."""

    stages: list[StagePerformanceItem] = Field(description="Per-stage performance statistics.")
    total_executions: int = Field(ge=0, description="Total stage execution attempts across all stages.")


class ReviewStatistics(BaseModel):
    """Workload and resolution metrics for the human-in-the-loop review queue."""

    total_reviews: int = Field(ge=0, description="Total reviews created.")
    pending_reviews: int = Field(ge=0, description="Reviews awaiting reviewer assignment.")
    in_review: int = Field(ge=0, description="Reviews currently being reviewed.")
    completed_reviews: int = Field(ge=0, description="Reviews that have been completed.")
    approved_reviews: int = Field(ge=0, description="Reviews where the decision was APPROVED.")
    rejected_reviews: int = Field(ge=0, description="Reviews where the decision was REJECTED.")
    corrected_reviews: int = Field(ge=0, description="Reviews where fields were corrected.")
    average_review_time_seconds: float | None = Field(
        default=None,
        description="Average time in seconds from review creation to completion.",
    )


class ProcessingVolumePoint(BaseModel):
    """A single time-bucket in the processing volume time series."""

    period: str = Field(description="Time bucket label (e.g. 'YYYY-MM-DD').")
    total: int = Field(ge=0, description="Total documents processed in this bucket.")
    completed: int = Field(ge=0, description="Documents successfully completed in this bucket.")
    failed: int = Field(ge=0, description="Documents that failed in this bucket.")


class ProcessingVolumeResponse(BaseModel):
    """Response containing time-series processing volume points."""

    points: list[ProcessingVolumePoint] = Field(description="Chronological time-series volume points.")
    interval: str = Field(description="Aggregation interval ('day' or 'week').")


class RecentActivityItem(BaseModel):
    """A single recent activity event from ProcessingHistory."""

    id: uuid.UUID = Field(description="History record identifier.")
    document_id: uuid.UUID = Field(description="Associated document ID.")
    document_filename: str = Field(description="Original document filename.")
    stage: str = Field(description="Pipeline stage name.")
    status: str = Field(description="Stage status (COMPLETED, FAILED, IN_PROGRESS, etc.).")
    message: str | None = Field(default=None, description="Event summary message.")
    started_at: datetime | None = Field(default=None, description="Stage start timestamp.")
    completed_at: datetime | None = Field(default=None, description="Stage completion timestamp.")
    duration_ms: float | None = Field(default=None, description="Execution duration in milliseconds.")


class RecentActivityResponse(BaseModel):
    """Response containing recent processing history events."""

    items: list[RecentActivityItem] = Field(description="Recent history events.")
    total: int = Field(ge=0, description="Count of returned events.")
