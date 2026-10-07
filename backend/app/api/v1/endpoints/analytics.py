"""
api/v1/endpoints/analytics.py
=============================
REST endpoints for the Analytics & Processing Observability module.

Provides:
- GET /api/v1/analytics/summary: High-level KPI metrics
- GET /api/v1/analytics/status-distribution: Documents grouped by DocumentStatus
- GET /api/v1/analytics/document-types: Documents grouped by DocumentType
- GET /api/v1/analytics/confidence: Confidence score averages and recommendation distribution
- GET /api/v1/analytics/stages: Processing stage executions, success rates, durations
- GET /api/v1/analytics/reviews: Review queue counts, decisions, and turnaround times
- GET /api/v1/analytics/volume: Time-series document throughput (day / week)
- GET /api/v1/analytics/recent-activity: Recent ProcessingHistory events
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.core.logging import get_logger
from app.schemas.analytics import (
    AnalyticsSummary,
    ConfidenceStatistics,
    DocumentTypeDistributionResponse,
    ProcessingVolumeResponse,
    RecentActivityResponse,
    ReviewStatistics,
    StagePerformanceResponse,
    StatusDistributionResponse,
)
from app.services.analytics_service import AnalyticsService

logger = get_logger("app.api.v1.endpoints.analytics")

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _validate_date_range(start_date: datetime | None, end_date: datetime | None) -> None:
    """Validate that start_date does not exceed end_date."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date.",
        )


@router.get(
    "/summary",
    response_model=AnalyticsSummary,
    status_code=status.HTTP_200_OK,
    summary="Get overall analytics KPI summary",
    description="Retrieve high-level KPIs including total documents, outcomes, average confidence, processing duration, and review metrics.",
)
async def get_summary(
    db: DbSession,
    start_date: Annotated[datetime | None, Query(description="Optional start timestamp filter (ISO-8601)")] = None,
    end_date: Annotated[datetime | None, Query(description="Optional end timestamp filter (ISO-8601)")] = None,
) -> AnalyticsSummary:
    _validate_date_range(start_date, end_date)
    service = AnalyticsService(db)
    return await service.get_document_summary(start_date=start_date, end_date=end_date)


@router.get(
    "/status-distribution",
    response_model=StatusDistributionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document status distribution",
    description="Retrieve document counts and percentages grouped by lifecycle status.",
)
async def get_status_distribution(
    db: DbSession,
    start_date: Annotated[datetime | None, Query(description="Optional start timestamp filter")] = None,
    end_date: Annotated[datetime | None, Query(description="Optional end timestamp filter")] = None,
) -> StatusDistributionResponse:
    _validate_date_range(start_date, end_date)
    service = AnalyticsService(db)
    return await service.get_status_distribution(start_date=start_date, end_date=end_date)


@router.get(
    "/document-types",
    response_model=DocumentTypeDistributionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document type distribution",
    description="Retrieve document counts and percentages grouped by detected document category.",
)
async def get_document_types(
    db: DbSession,
    start_date: Annotated[datetime | None, Query(description="Optional start timestamp filter")] = None,
    end_date: Annotated[datetime | None, Query(description="Optional end timestamp filter")] = None,
) -> DocumentTypeDistributionResponse:
    _validate_date_range(start_date, end_date)
    service = AnalyticsService(db)
    return await service.get_document_type_distribution(start_date=start_date, end_date=end_date)


@router.get(
    "/confidence",
    response_model=ConfidenceStatistics,
    status_code=status.HTTP_200_OK,
    summary="Get confidence scoring statistics",
    description="Retrieve aggregate confidence averages, extremes, and auto-approve vs review-required distribution.",
)
async def get_confidence_statistics(
    db: DbSession,
    start_date: Annotated[datetime | None, Query(description="Optional start timestamp filter")] = None,
    end_date: Annotated[datetime | None, Query(description="Optional end timestamp filter")] = None,
) -> ConfidenceStatistics:
    _validate_date_range(start_date, end_date)
    service = AnalyticsService(db)
    return await service.get_confidence_statistics(start_date=start_date, end_date=end_date)


@router.get(
    "/stages",
    response_model=StagePerformanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get stage execution performance",
    description="Retrieve total executions, completed, failed, success rate, and average duration in milliseconds per pipeline stage.",
)
async def get_stages(
    db: DbSession,
    start_date: Annotated[datetime | None, Query(description="Optional start timestamp filter")] = None,
    end_date: Annotated[datetime | None, Query(description="Optional end timestamp filter")] = None,
) -> StagePerformanceResponse:
    _validate_date_range(start_date, end_date)
    service = AnalyticsService(db)
    return await service.get_stage_performance(start_date=start_date, end_date=end_date)


@router.get(
    "/reviews",
    response_model=ReviewStatistics,
    status_code=status.HTTP_200_OK,
    summary="Get review queue statistics",
    description="Retrieve counts of pending, active, and completed reviews, decisions breakdown, and average review resolution time.",
)
async def get_reviews(
    db: DbSession,
    start_date: Annotated[datetime | None, Query(description="Optional start timestamp filter")] = None,
    end_date: Annotated[datetime | None, Query(description="Optional end timestamp filter")] = None,
) -> ReviewStatistics:
    _validate_date_range(start_date, end_date)
    service = AnalyticsService(db)
    return await service.get_review_statistics(start_date=start_date, end_date=end_date)


@router.get(
    "/volume",
    response_model=ProcessingVolumeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document processing volume over time",
    description="Retrieve time-series counts of documents processed over day or week intervals.",
)
async def get_volume(
    db: DbSession,
    start_date: Annotated[datetime | None, Query(description="Optional start timestamp filter")] = None,
    end_date: Annotated[datetime | None, Query(description="Optional end timestamp filter")] = None,
    interval: Annotated[str, Query(description="Time bucket interval: 'day' or 'week'")] = "day",
) -> ProcessingVolumeResponse:
    _validate_date_range(start_date, end_date)
    service = AnalyticsService(db)
    return await service.get_processing_volume(
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )


@router.get(
    "/recent-activity",
    response_model=RecentActivityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recent processing activity",
    description="Retrieve a chronological stream of the latest processing history events with duration metrics.",
)
async def get_recent_activity(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of history items to return (1-100)")] = 20,
) -> RecentActivityResponse:
    service = AnalyticsService(db)
    return await service.get_recent_activity(limit=limit)
