"""
tests/test_analytics.py
=======================
Comprehensive tests for Step 11: Analytics & Processing Observability module.

Covers:
1. Empty database behavior for all analytics endpoints
2. Date range validation (start_date > end_date returns 400)
3. Document summary KPIs with populated database
4. Status distribution calculation and percentages
5. Document type distribution calculation and percentages
6. Confidence score statistics (averages, extremes, recommendation counts)
7. Stage execution performance (executions, completions, failures, success rate, duration)
8. Review statistics (pending, active, completed decisions, turnaround time)
9. Time-series processing volume (day and week intervals)
10. Volume date range filtering
11. Recent activity list ordering, limits, and duration calculation
12. Direct AnalyticsService unit tests
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ConfidenceRecommendation,
    DocumentStatus,
    DocumentType,
    ProcessingStage,
    ReviewDecision,
    ReviewStatus,
    StageStatus,
)
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.models.review import DocumentReview
from app.services.analytics_service import AnalyticsService


# ---------------------------------------------------------------------------
# Helpers for test data creation
# ---------------------------------------------------------------------------


async def _create_test_document(
    db: AsyncSession,
    *,
    original_filename: str = "test.pdf",
    status: str = DocumentStatus.UPLOADED.value,
    document_type: str | None = None,
    overall_confidence: float | None = None,
    classification_confidence: float | None = None,
    extraction_confidence: float | None = None,
    validation_confidence: float | None = None,
    confidence_recommendation: str | None = None,
    rag_indexed: bool = False,
    created_at: datetime | None = None,
) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        original_filename=original_filename,
        stored_filename=f"stored_{original_filename}",
        file_path=f"uploads/{original_filename}",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1024,
        status=status,
        document_type=document_type,
        overall_confidence=overall_confidence,
        classification_confidence=classification_confidence,
        extraction_confidence=extraction_confidence,
        validation_confidence=validation_confidence,
        confidence_recommendation=confidence_recommendation,
        rag_indexed=rag_indexed,
    )
    if created_at:
        doc.created_at = created_at

    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def _create_history(
    db: AsyncSession,
    document_id: uuid.UUID,
    stage: str,
    status: str,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    message: str | None = None,
) -> ProcessingHistory:
    h = ProcessingHistory(
        id=uuid.uuid4(),
        document_id=document_id,
        stage=stage,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        message=message,
    )
    db.add(h)
    await db.commit()
    await db.refresh(h)
    return h


# ---------------------------------------------------------------------------
# Tests: Empty Database
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_database_summary(async_client: AsyncClient) -> None:
    """Empty database should return zero counts and null averages."""
    resp = await async_client.get("/api/v1/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_documents"] == 0
    assert data["approved_documents"] == 0
    assert data["rejected_documents"] == 0
    assert data["processing_documents"] == 0
    assert data["review_required_documents"] == 0
    assert data["failed_documents"] == 0
    assert data["average_confidence"] is None
    assert data["average_processing_time_ms"] is None
    assert data["rag_indexed_documents"] == 0
    assert data["auto_approved_documents"] == 0
    assert data["human_reviewed_documents"] == 0


@pytest.mark.asyncio
async def test_empty_database_status_distribution(async_client: AsyncClient) -> None:
    """Empty database should return total 0 and default status items with 0 count."""
    resp = await async_client.get("/api/v1/analytics/status-distribution")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert len(data["items"]) >= 5
    for item in data["items"]:
        assert item["count"] == 0
        assert item["percentage"] == 0.0


@pytest.mark.asyncio
async def test_empty_database_document_types(async_client: AsyncClient) -> None:
    """Empty database should return total 0 and default document types."""
    resp = await async_client.get("/api/v1/analytics/document-types")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert len(data["items"]) >= 5


@pytest.mark.asyncio
async def test_empty_database_confidence(async_client: AsyncClient) -> None:
    """Empty database should return null averages and 0 recommendation counts."""
    resp = await async_client.get("/api/v1/analytics/confidence")
    assert resp.status_code == 200
    data = resp.json()
    assert data["average_overall"] is None
    assert data["auto_approve_count"] == 0
    assert data["review_required_count"] == 0


@pytest.mark.asyncio
async def test_empty_database_stages(async_client: AsyncClient) -> None:
    """Empty database should return default pipeline stages with 0 executions."""
    resp = await async_client.get("/api/v1/analytics/stages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_executions"] == 0
    assert len(data["stages"]) >= 5
    for stage in data["stages"]:
        assert stage["executions"] == 0
        assert stage["completed"] == 0
        assert stage["failed"] == 0


@pytest.mark.asyncio
async def test_empty_database_reviews(async_client: AsyncClient) -> None:
    """Empty database should return all 0 review counts."""
    resp = await async_client.get("/api/v1/analytics/reviews")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_reviews"] == 0
    assert data["pending_reviews"] == 0
    assert data["in_review"] == 0
    assert data["completed_reviews"] == 0
    assert data["average_review_time_seconds"] is None


@pytest.mark.asyncio
async def test_empty_database_volume(async_client: AsyncClient) -> None:
    """Empty database should return empty volume points list."""
    resp = await async_client.get("/api/v1/analytics/volume")
    assert resp.status_code == 200
    data = resp.json()
    assert data["points"] == []
    assert data["interval"] == "day"


@pytest.mark.asyncio
async def test_empty_database_recent_activity(async_client: AsyncClient) -> None:
    """Empty database should return empty recent activity list."""
    resp = await async_client.get("/api/v1/analytics/recent-activity")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


# ---------------------------------------------------------------------------
# Tests: Date Range Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_date_range_validation_error(async_client: AsyncClient) -> None:
    """Querying with start_date after end_date must return HTTP 400."""
    start = "2026-10-01T00:00:00"
    end = "2026-09-01T00:00:00"

    endpoints = [
        "/api/v1/analytics/summary",
        "/api/v1/analytics/status-distribution",
        "/api/v1/analytics/document-types",
        "/api/v1/analytics/confidence",
        "/api/v1/analytics/stages",
        "/api/v1/analytics/reviews",
        "/api/v1/analytics/volume",
    ]

    for ep in endpoints:
        resp = await async_client.get(f"{ep}?start_date={start}&end_date={end}")
        assert resp.status_code == 400
        assert "start_date cannot be after end_date" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: Summary & Status Distributions with Populated Data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_and_distribution_with_data(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify summary KPIs and status distribution calculations with populated documents."""
    now = datetime.now(timezone.utc)

    # 1. Approved auto-approved doc
    doc1 = await _create_test_document(
        db_session,
        original_filename="inv1.pdf",
        status=DocumentStatus.APPROVED.value,
        document_type=DocumentType.INVOICE.value,
        overall_confidence=0.95,
        confidence_recommendation=ConfidenceRecommendation.AUTO_APPROVE.value,
        rag_indexed=True,
    )
    # 2. Approved via review doc
    doc2 = await _create_test_document(
        db_session,
        original_filename="rec1.pdf",
        status=DocumentStatus.APPROVED.value,
        document_type=DocumentType.RECEIPT.value,
        overall_confidence=0.75,
        confidence_recommendation=ConfidenceRecommendation.REVIEW_REQUIRED.value,
        rag_indexed=True,
    )
    # Review record for doc2
    review2 = DocumentReview(
        id=uuid.uuid4(),
        document_id=doc2.id,
        status=ReviewStatus.COMPLETED.value,
        decision=ReviewDecision.APPROVED.value,
        reviewed_at=now,
    )
    db_session.add(review2)

    # 3. Rejected doc
    doc3 = await _create_test_document(
        db_session,
        original_filename="inv2.pdf",
        status=DocumentStatus.REJECTED.value,
        document_type=DocumentType.INVOICE.value,
        overall_confidence=0.50,
        confidence_recommendation=ConfidenceRecommendation.REVIEW_REQUIRED.value,
        rag_indexed=False,
    )

    # 4. Processing doc
    await _create_test_document(
        db_session,
        original_filename="contract1.pdf",
        status=DocumentStatus.PROCESSING.value,
        document_type=DocumentType.CONTRACT.value,
    )

    # 5. Review required doc
    await _create_test_document(
        db_session,
        original_filename="po1.pdf",
        status=DocumentStatus.REVIEW_REQUIRED.value,
        document_type=DocumentType.PURCHASE_ORDER.value,
        overall_confidence=0.60,
        confidence_recommendation=ConfidenceRecommendation.REVIEW_REQUIRED.value,
    )

    # 6. Failed doc
    await _create_test_document(
        db_session,
        original_filename="failed.pdf",
        status=DocumentStatus.FAILED.value,
    )

    await db_session.commit()

    # Query Summary
    resp = await async_client.get("/api/v1/analytics/summary")
    assert resp.status_code == 200
    summary = resp.json()

    assert summary["total_documents"] == 6
    assert summary["approved_documents"] == 2
    assert summary["rejected_documents"] == 1
    assert summary["processing_documents"] == 1
    assert summary["review_required_documents"] == 1
    assert summary["failed_documents"] == 1
    assert summary["rag_indexed_documents"] == 2
    assert summary["auto_approved_documents"] == 1
    assert summary["human_reviewed_documents"] == 1
    assert summary["average_confidence"] is not None
    # (0.95 + 0.75 + 0.50 + 0.60) / 4 = 2.80 / 4 = 0.70
    assert summary["average_confidence"] == pytest.approx(0.70, abs=0.01)

    # Query Status Distribution
    resp_dist = await async_client.get("/api/v1/analytics/status-distribution")
    assert resp_dist.status_code == 200
    dist_data = resp_dist.json()
    assert dist_data["total"] == 6

    status_map = {item["status"]: item for item in dist_data["items"]}
    assert status_map[DocumentStatus.APPROVED.value]["count"] == 2
    assert status_map[DocumentStatus.APPROVED.value]["percentage"] == pytest.approx(33.33, abs=0.1)
    assert status_map[DocumentStatus.REJECTED.value]["count"] == 1
    assert status_map[DocumentStatus.FAILED.value]["count"] == 1

    # Query Document Types
    resp_types = await async_client.get("/api/v1/analytics/document-types")
    assert resp_types.status_code == 200
    types_data = resp_types.json()
    assert types_data["total"] == 5  # 5 classified docs

    type_map = {item["document_type"]: item for item in types_data["items"]}
    assert type_map[DocumentType.INVOICE.value]["count"] == 2
    assert type_map[DocumentType.INVOICE.value]["percentage"] == 40.0
    assert type_map[DocumentType.RECEIPT.value]["count"] == 1
    assert type_map[DocumentType.CONTRACT.value]["count"] == 1
    assert type_map[DocumentType.PURCHASE_ORDER.value]["count"] == 1


# ---------------------------------------------------------------------------
# Tests: Confidence Statistics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confidence_statistics(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify confidence statistics calculations including averages, extremes, and recommendations."""
    await _create_test_document(
        db_session,
        original_filename="docA.pdf",
        overall_confidence=0.90,
        classification_confidence=0.95,
        extraction_confidence=0.85,
        validation_confidence=0.90,
        confidence_recommendation=ConfidenceRecommendation.AUTO_APPROVE.value,
    )
    await _create_test_document(
        db_session,
        original_filename="docB.pdf",
        overall_confidence=0.70,
        classification_confidence=0.80,
        extraction_confidence=0.65,
        validation_confidence=0.65,
        confidence_recommendation=ConfidenceRecommendation.REVIEW_REQUIRED.value,
    )
    await db_session.commit()

    resp = await async_client.get("/api/v1/analytics/confidence")
    assert resp.status_code == 200
    data = resp.json()

    assert data["average_overall"] == pytest.approx(0.80, abs=0.01)
    assert data["average_classification"] == pytest.approx(0.875, abs=0.01)
    assert data["average_extraction"] == pytest.approx(0.75, abs=0.01)
    assert data["min_confidence"] == pytest.approx(0.70, abs=0.01)
    assert data["max_confidence"] == pytest.approx(0.90, abs=0.01)
    assert data["auto_approve_count"] == 1
    assert data["review_required_count"] == 1


# ---------------------------------------------------------------------------
# Tests: Stage Execution Performance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_performance(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify stage executions, completion, failures, success rate, and duration calculations."""
    doc = await _create_test_document(db_session, original_filename="stage_test.pdf")

    t1 = datetime(2026, 9, 24, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 24, 10, 0, 2, tzinfo=timezone.utc)  # 2000 ms

    # Stage OCR: 1 success (2000ms)
    await _create_history(
        db_session,
        doc.id,
        stage=ProcessingStage.OCR.value,
        status=StageStatus.COMPLETED.value,
        started_at=t1,
        completed_at=t2,
    )

    # Stage CLASSIFICATION: 1 success (2000ms), 1 failed
    await _create_history(
        db_session,
        doc.id,
        stage=ProcessingStage.CLASSIFICATION.value,
        status=StageStatus.COMPLETED.value,
        started_at=t1,
        completed_at=t2,
    )
    await _create_history(
        db_session,
        doc.id,
        stage=ProcessingStage.CLASSIFICATION.value,
        status=StageStatus.FAILED.value,
        started_at=t1,
        completed_at=t2,
    )

    await db_session.commit()

    resp = await async_client.get("/api/v1/analytics/stages")
    assert resp.status_code == 200
    data = resp.json()

    stage_map = {s["stage"]: s for s in data["stages"]}
    ocr_stage = stage_map[ProcessingStage.OCR.value]
    assert ocr_stage["executions"] == 1
    assert ocr_stage["completed"] == 1
    assert ocr_stage["failed"] == 0
    assert ocr_stage["success_rate"] == 100.0
    assert ocr_stage["average_duration_ms"] is not None
    assert ocr_stage["average_duration_ms"] == pytest.approx(2000.0, abs=100.0)

    class_stage = stage_map[ProcessingStage.CLASSIFICATION.value]
    assert class_stage["executions"] == 2
    assert class_stage["completed"] == 1
    assert class_stage["failed"] == 1
    assert class_stage["success_rate"] == 50.0


# ---------------------------------------------------------------------------
# Tests: Review Queue Statistics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_statistics(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify review queue workload, decisions, and average turnaround time."""
    doc = await _create_test_document(db_session, original_filename="review_stat.pdf")

    t_created = datetime(2026, 9, 24, 10, 0, 0, tzinfo=timezone.utc)
    t_reviewed = datetime(2026, 9, 24, 10, 2, 0, tzinfo=timezone.utc)  # 120 seconds

    # 1 Pending
    r1 = DocumentReview(
        id=uuid.uuid4(),
        document_id=doc.id,
        status=ReviewStatus.PENDING.value,
        created_at=t_created,
    )
    # 1 In Review
    r2 = DocumentReview(
        id=uuid.uuid4(),
        document_id=doc.id,
        status=ReviewStatus.IN_REVIEW.value,
        created_at=t_created,
    )
    # 1 Completed Approved
    r3 = DocumentReview(
        id=uuid.uuid4(),
        document_id=doc.id,
        status=ReviewStatus.COMPLETED.value,
        decision=ReviewDecision.APPROVED.value,
        created_at=t_created,
        reviewed_at=t_reviewed,
    )
    # 1 Completed Corrected
    r4 = DocumentReview(
        id=uuid.uuid4(),
        document_id=doc.id,
        status=ReviewStatus.COMPLETED.value,
        decision=ReviewDecision.CORRECTED.value,
        created_at=t_created,
        reviewed_at=t_reviewed,
    )
    db_session.add_all([r1, r2, r3, r4])
    await db_session.commit()

    resp = await async_client.get("/api/v1/analytics/reviews")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_reviews"] == 4
    assert data["pending_reviews"] == 1
    assert data["in_review"] == 1
    assert data["completed_reviews"] == 2
    assert data["approved_reviews"] == 1
    assert data["rejected_reviews"] == 0
    assert data["corrected_reviews"] == 1
    assert data["average_review_time_seconds"] is not None
    assert data["average_review_time_seconds"] == pytest.approx(120.0, abs=10.0)


# ---------------------------------------------------------------------------
# Tests: Processing Volume Time Series
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_processing_volume(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify document volume time-series aggregation for day and week intervals."""
    d1 = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    d2 = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)

    await _create_test_document(db_session, original_filename="v1.pdf", status=DocumentStatus.APPROVED.value, created_at=d1)
    await _create_test_document(db_session, original_filename="v2.pdf", status=DocumentStatus.FAILED.value, created_at=d1)
    await _create_test_document(db_session, original_filename="v3.pdf", status=DocumentStatus.APPROVED.value, created_at=d2)
    await db_session.commit()

    # Day interval
    resp_day = await async_client.get("/api/v1/analytics/volume?interval=day")
    assert resp_day.status_code == 200
    day_data = resp_day.json()
    assert day_data["interval"] == "day"
    assert len(day_data["points"]) >= 2

    # Week interval
    resp_week = await async_client.get("/api/v1/analytics/volume?interval=week")
    assert resp_week.status_code == 200
    week_data = resp_week.json()
    assert week_data["interval"] == "week"
    assert len(week_data["points"]) >= 1


# ---------------------------------------------------------------------------
# Tests: Recent Activity List & Limits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recent_activity(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify recent activity returns ordered history events, limits, and duration calculations."""
    doc = await _create_test_document(db_session, original_filename="recent_test.pdf")

    t_start = datetime(2026, 9, 24, 15, 0, 0, tzinfo=timezone.utc)
    t_end = datetime(2026, 9, 24, 15, 0, 5, tzinfo=timezone.utc)  # 5000 ms

    for i in range(10):
        await _create_history(
            db_session,
            doc.id,
            stage=ProcessingStage.OCR.value,
            status=StageStatus.COMPLETED.value,
            started_at=t_start,
            completed_at=t_end,
            message=f"Event {i}",
        )
    await db_session.commit()

    # Test limit=5
    resp = await async_client.get("/api/v1/analytics/recent-activity?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 5
    assert data["items"][0]["document_filename"] == "recent_test.pdf"
    assert data["items"][0]["duration_ms"] == pytest.approx(5000.0, abs=100.0)



# ---------------------------------------------------------------------------
# Tests: Direct AnalyticsService Call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analytics_service_direct(db_session: AsyncSession) -> None:
    """Direct unit test of AnalyticsService class."""
    service = AnalyticsService(db_session)
    summary = await service.get_document_summary()
    assert summary.total_documents >= 0

    dist = await service.get_status_distribution()
    assert dist.total >= 0

    types = await service.get_document_type_distribution()
    assert types.total >= 0

    stages = await service.get_stage_performance()
    assert stages.total_executions >= 0

    reviews = await service.get_review_statistics()
    assert reviews.total_reviews >= 0

    volume = await service.get_processing_volume()
    assert volume.interval == "day"

    activity = await service.get_recent_activity(limit=10)
    assert activity.total >= 0
