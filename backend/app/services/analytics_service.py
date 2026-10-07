"""
services/analytics_service.py
==============================
Read-only analytics and observability aggregation service.

Calculates KPIs, status distributions, stage execution performance,
review queue workload, time-series processing volume, and recent audit logs
using database-driven aggregations.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from sqlalchemy import case, func, select
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
from app.core.logging import get_logger
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.models.review import DocumentReview
from app.schemas.analytics import (
    AnalyticsSummary,
    ConfidenceStatistics,
    DocumentTypeDistributionItem,
    DocumentTypeDistributionResponse,
    ProcessingVolumePoint,
    ProcessingVolumeResponse,
    RecentActivityItem,
    RecentActivityResponse,
    ReviewStatistics,
    StagePerformanceItem,
    StagePerformanceResponse,
    StatusDistributionItem,
    StatusDistributionResponse,
)

logger = get_logger("app.services.analytics")


def _is_sqlite(session: AsyncSession) -> bool:
    """Check if the underlying database connection is SQLite."""
    bind = session.get_bind()
    return bool(bind and bind.dialect.name == "sqlite")


def _duration_ms_expr(session: AsyncSession, start_col: Any, end_col: Any):
    """SQL expression returning duration in milliseconds across PostgreSQL and SQLite."""
    if _is_sqlite(session):
        return (func.julianday(end_col) - func.julianday(start_col)) * 86400000.0
    return func.extract("epoch", end_col - start_col) * 1000.0


def _duration_seconds_expr(session: AsyncSession, start_col: Any, end_col: Any):
    """SQL expression returning duration in seconds across PostgreSQL and SQLite."""
    if _is_sqlite(session):
        return (func.julianday(end_col) - func.julianday(start_col)) * 86400.0
    return func.extract("epoch", end_col - start_col)


class AnalyticsService:
    """Read-only service for aggregate document processing analytics."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_document_summary(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> AnalyticsSummary:
        """
        Aggregate high-level processing KPIs.
        """
        # Base document query with date filters
        doc_stmt = select(
            func.count(Document.id).label("total"),
            func.count(case((Document.status == DocumentStatus.APPROVED.value, 1))).label("approved"),
            func.count(case((Document.status == DocumentStatus.REJECTED.value, 1))).label("rejected"),
            func.count(
                case(
                    (
                        Document.status.in_(
                            [
                                DocumentStatus.PROCESSING.value,
                                DocumentStatus.OCR_COMPLETED.value,
                                DocumentStatus.CLASSIFIED.value,
                                DocumentStatus.EXTRACTED.value,
                                DocumentStatus.VALIDATED.value,
                            ]
                        ),
                        1,
                    )
                )
            ).label("processing"),
            func.count(case((Document.status == DocumentStatus.REVIEW_REQUIRED.value, 1))).label("review_required"),
            func.count(case((Document.status == DocumentStatus.FAILED.value, 1))).label("failed"),
            func.avg(Document.overall_confidence).label("avg_confidence"),
            func.count(case((Document.rag_indexed.is_(True), 1))).label("rag_indexed"),
            func.count(
                case(
                    (
                        (Document.status == DocumentStatus.APPROVED.value)
                        & (Document.confidence_recommendation == ConfidenceRecommendation.AUTO_APPROVE.value),
                        1,
                    )
                )
            ).label("auto_approved"),
        )

        if start_date:
            doc_stmt = doc_stmt.where(Document.created_at >= start_date)
        if end_date:
            doc_stmt = doc_stmt.where(Document.created_at <= end_date)

        doc_result = await self.db.execute(doc_stmt)
        row = doc_result.fetchone()

        total = row.total or 0 if row else 0
        approved = row.approved or 0 if row else 0
        rejected = row.rejected or 0 if row else 0
        processing = row.processing or 0 if row else 0
        review_required = row.review_required or 0 if row else 0
        failed = row.failed or 0 if row else 0
        avg_confidence = round(float(row.avg_confidence), 4) if (row and row.avg_confidence is not None) else None
        rag_indexed = row.rag_indexed or 0 if row else 0
        auto_approved = row.auto_approved or 0 if row else 0

        # Human reviewed count: distinct documents with completed reviews
        review_stmt = select(func.count(func.distinct(DocumentReview.document_id))).where(
            DocumentReview.status == ReviewStatus.COMPLETED.value
        )
        if start_date:
            review_stmt = review_stmt.where(DocumentReview.created_at >= start_date)
        if end_date:
            review_stmt = review_stmt.where(DocumentReview.created_at <= end_date)

        review_result = await self.db.execute(review_stmt)
        human_reviewed = review_result.scalar() or 0

        # Average processing duration per document from ProcessingHistory
        # Sum of duration across stages for completed documents
        duration_expr = _duration_ms_expr(self.db, ProcessingHistory.started_at, ProcessingHistory.completed_at)
        history_stmt = (
            select(func.avg(duration_expr))
            .where(
                ProcessingHistory.status == StageStatus.COMPLETED.value,
                ProcessingHistory.started_at.isnot(None),
                ProcessingHistory.completed_at.isnot(None),
            )
        )
        if start_date:
            history_stmt = history_stmt.where(ProcessingHistory.created_at >= start_date)
        if end_date:
            history_stmt = history_stmt.where(ProcessingHistory.created_at <= end_date)

        history_result = await self.db.execute(history_stmt)
        avg_processing_time = history_result.scalar()
        avg_processing_time_ms = round(float(avg_processing_time), 2) if avg_processing_time is not None else None

        return AnalyticsSummary(
            total_documents=total,
            approved_documents=approved,
            rejected_documents=rejected,
            processing_documents=processing,
            review_required_documents=review_required,
            failed_documents=failed,
            average_confidence=avg_confidence,
            average_processing_time_ms=avg_processing_time_ms,
            rag_indexed_documents=rag_indexed,
            auto_approved_documents=auto_approved,
            human_reviewed_documents=human_reviewed,
        )

    async def get_status_distribution(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> StatusDistributionResponse:
        """
        Return the distribution of documents by status.
        """
        stmt = select(Document.status, func.count(Document.id)).group_by(Document.status)
        if start_date:
            stmt = stmt.where(Document.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Document.created_at <= end_date)

        result = await self.db.execute(stmt)
        rows = result.all()

        total = sum(count for _, count in rows)
        items = [
            StatusDistributionItem(
                status=status,
                count=count,
                percentage=round((count / total * 100.0), 2) if total > 0 else 0.0,
            )
            for status, count in rows
        ]

        # Ensure all core statuses are represented if empty
        existing_statuses = {item.status for item in items}
        for expected in [
            DocumentStatus.UPLOADED.value,
            DocumentStatus.PROCESSING.value,
            DocumentStatus.APPROVED.value,
            DocumentStatus.REVIEW_REQUIRED.value,
            DocumentStatus.REJECTED.value,
            DocumentStatus.FAILED.value,
        ]:
            if expected not in existing_statuses:
                items.append(StatusDistributionItem(status=expected, count=0, percentage=0.0))

        # Sort with most frequent first
        items.sort(key=lambda x: x.count, reverse=True)

        return StatusDistributionResponse(items=items, total=total)

    async def get_document_type_distribution(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> DocumentTypeDistributionResponse:
        """
        Return the distribution of classified document types.
        """
        stmt = (
            select(Document.document_type, func.count(Document.id))
            .where(Document.document_type.isnot(None))
            .group_by(Document.document_type)
        )
        if start_date:
            stmt = stmt.where(Document.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Document.created_at <= end_date)

        result = await self.db.execute(stmt)
        rows = result.all()

        total = sum(count for _, count in rows)
        items = [
            DocumentTypeDistributionItem(
                document_type=doc_type,
                count=count,
                percentage=round((count / total * 100.0), 2) if total > 0 else 0.0,
            )
            for doc_type, count in rows
        ]

        # Ensure standard DocumentType enums are present
        existing_types = {item.document_type for item in items}
        for expected in [
            DocumentType.INVOICE.value,
            DocumentType.RECEIPT.value,
            DocumentType.PURCHASE_ORDER.value,
            DocumentType.CONTRACT.value,
            DocumentType.OTHER.value,
        ]:
            if expected not in existing_types:
                items.append(DocumentTypeDistributionItem(document_type=expected, count=0, percentage=0.0))

        items.sort(key=lambda x: x.count, reverse=True)
        return DocumentTypeDistributionResponse(items=items, total=total)

    async def get_confidence_statistics(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> ConfidenceStatistics:
        """
        Return aggregate confidence score metrics.
        """
        stmt = select(
            func.avg(Document.overall_confidence).label("avg_overall"),
            func.avg(Document.classification_confidence).label("avg_classification"),
            func.avg(Document.extraction_confidence).label("avg_extraction"),
            func.avg(Document.validation_confidence).label("avg_validation"),
            func.min(Document.overall_confidence).label("min_confidence"),
            func.max(Document.overall_confidence).label("max_confidence"),
            func.count(
                case((Document.confidence_recommendation == ConfidenceRecommendation.AUTO_APPROVE.value, 1))
            ).label("auto_approve"),
            func.count(
                case((Document.confidence_recommendation == ConfidenceRecommendation.REVIEW_REQUIRED.value, 1))
            ).label("review_required"),
        )
        if start_date:
            stmt = stmt.where(Document.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Document.created_at <= end_date)

        result = await self.db.execute(stmt)
        row = result.fetchone()

        def _fmt(val: Any) -> float | None:
            return round(float(val), 4) if val is not None else None

        return ConfidenceStatistics(
            average_overall=_fmt(row.avg_overall) if row else None,
            average_classification=_fmt(row.avg_classification) if row else None,
            average_extraction=_fmt(row.avg_extraction) if row else None,
            average_validation=_fmt(row.avg_validation) if row else None,
            min_confidence=_fmt(row.min_confidence) if row else None,
            max_confidence=_fmt(row.max_confidence) if row else None,
            auto_approve_count=row.auto_approve if row else 0,
            review_required_count=row.review_required if row else 0,
        )

    async def get_stage_performance(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> StagePerformanceResponse:
        """
        Return execution counts, success rates, and average duration per stage.
        """
        duration_expr = _duration_ms_expr(self.db, ProcessingHistory.started_at, ProcessingHistory.completed_at)

        stmt = (
            select(
                ProcessingHistory.stage,
                func.count(ProcessingHistory.id).label("executions"),
                func.count(case((ProcessingHistory.status == StageStatus.COMPLETED.value, 1))).label("completed"),
                func.count(case((ProcessingHistory.status == StageStatus.FAILED.value, 1))).label("failed"),
                func.avg(
                    case(
                        (
                            (ProcessingHistory.status == StageStatus.COMPLETED.value)
                            & ProcessingHistory.started_at.isnot(None)
                            & ProcessingHistory.completed_at.isnot(None),
                            duration_expr,
                        )
                    )
                ).label("avg_duration"),
            )
            .group_by(ProcessingHistory.stage)
        )

        if start_date:
            stmt = stmt.where(ProcessingHistory.created_at >= start_date)
        if end_date:
            stmt = stmt.where(ProcessingHistory.created_at <= end_date)

        result = await self.db.execute(stmt)
        rows = result.all()

        stages: list[StagePerformanceItem] = []
        total_executions = 0

        for row in rows:
            executions = row.executions or 0
            completed = row.completed or 0
            failed = row.failed or 0
            avg_dur = round(float(row.avg_duration), 2) if row.avg_duration is not None else None
            success_rate = round((completed / executions * 100.0), 2) if executions > 0 else 0.0

            total_executions += executions
            stages.append(
                StagePerformanceItem(
                    stage=row.stage,
                    executions=executions,
                    completed=completed,
                    failed=failed,
                    average_duration_ms=avg_dur,
                    success_rate=success_rate,
                )
            )

        # Ensure major pipeline stages appear even if not yet executed
        major_stages = [
            ProcessingStage.UPLOAD.value,
            ProcessingStage.OCR.value,
            ProcessingStage.CLASSIFICATION.value,
            ProcessingStage.EXTRACTION.value,
            ProcessingStage.VALIDATION.value,
            ProcessingStage.CONFIDENCE_SCORING.value,
        ]
        present = {s.stage for s in stages}
        for expected in major_stages:
            if expected not in present:
                stages.append(
                    StagePerformanceItem(
                        stage=expected,
                        executions=0,
                        completed=0,
                        failed=0,
                        average_duration_ms=None,
                        success_rate=100.0,
                    )
                )

        return StagePerformanceResponse(stages=stages, total_executions=total_executions)

    async def get_review_statistics(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> ReviewStatistics:
        """
        Return workload and turnaround metrics for the review queue.
        """
        duration_seconds = _duration_seconds_expr(self.db, DocumentReview.created_at, DocumentReview.reviewed_at)

        stmt = select(
            func.count(DocumentReview.id).label("total"),
            func.count(case((DocumentReview.status == ReviewStatus.PENDING.value, 1))).label("pending"),
            func.count(case((DocumentReview.status == ReviewStatus.IN_REVIEW.value, 1))).label("in_review"),
            func.count(case((DocumentReview.status == ReviewStatus.COMPLETED.value, 1))).label("completed"),
            func.count(case((DocumentReview.decision == ReviewDecision.APPROVED.value, 1))).label("approved"),
            func.count(case((DocumentReview.decision == ReviewDecision.REJECTED.value, 1))).label("rejected"),
            func.count(case((DocumentReview.decision == ReviewDecision.CORRECTED.value, 1))).label("corrected"),
            func.avg(
                case(
                    (
                        (DocumentReview.status == ReviewStatus.COMPLETED.value)
                        & DocumentReview.reviewed_at.isnot(None),
                        duration_seconds,
                    )
                )
            ).label("avg_review_seconds"),
        )

        if start_date:
            stmt = stmt.where(DocumentReview.created_at >= start_date)
        if end_date:
            stmt = stmt.where(DocumentReview.created_at <= end_date)

        result = await self.db.execute(stmt)
        row = result.fetchone()

        avg_time = round(float(row.avg_review_seconds), 2) if (row and row.avg_review_seconds is not None) else None

        return ReviewStatistics(
            total_reviews=row.total if row else 0,
            pending_reviews=row.pending if row else 0,
            in_review=row.in_review if row else 0,
            completed_reviews=row.completed if row else 0,
            approved_reviews=row.approved if row else 0,
            rejected_reviews=row.rejected if row else 0,
            corrected_reviews=row.corrected if row else 0,
            average_review_time_seconds=avg_time,
        )

    async def get_processing_volume(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        interval: str = "day",
    ) -> ProcessingVolumeResponse:
        """
        Aggregate document volume over time (day or week).
        """
        interval = interval.lower()
        if interval not in ("day", "week"):
            interval = "day"

        is_sqlite = _is_sqlite(self.db)
        if is_sqlite:
            period_expr = (
                func.strftime("%Y-%m-%d", Document.created_at)
                if interval == "day"
                else func.strftime("%Y-W%W", Document.created_at)
            )
        else:
            period_expr = (
                func.to_char(func.date_trunc("day", Document.created_at), "YYYY-MM-DD")
                if interval == "day"
                else func.to_char(func.date_trunc("week", Document.created_at), 'IYYY-"W"IW')
            )

        stmt = (
            select(
                period_expr.label("period"),
                func.count(Document.id).label("total"),
                func.count(case((Document.status == DocumentStatus.APPROVED.value, 1))).label("completed"),
                func.count(case((Document.status == DocumentStatus.FAILED.value, 1))).label("failed"),
            )
            .group_by(period_expr)
            .order_by(period_expr.asc())
        )

        if start_date:
            stmt = stmt.where(Document.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Document.created_at <= end_date)

        result = await self.db.execute(stmt)
        rows = result.all()

        points = [
            ProcessingVolumePoint(
                period=str(row.period or ""),
                total=row.total or 0,
                completed=row.completed or 0,
                failed=row.failed or 0,
            )
            for row in rows
        ]

        return ProcessingVolumeResponse(points=points, interval=interval)

    async def get_recent_activity(
        self,
        limit: int = 20,
    ) -> RecentActivityResponse:
        """
        Return latest processing history events.
        """
        limit = max(1, min(100, limit))

        stmt = (
            select(
                ProcessingHistory.id,
                ProcessingHistory.document_id,
                Document.original_filename,
                ProcessingHistory.stage,
                ProcessingHistory.status,
                ProcessingHistory.message,
                ProcessingHistory.started_at,
                ProcessingHistory.completed_at,
            )
            .join(Document, ProcessingHistory.document_id == Document.id)
            .order_by(ProcessingHistory.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        items: list[RecentActivityItem] = []
        for row in rows:
            dur: float | None = None
            if row.started_at and row.completed_at:
                dur = round((row.completed_at - row.started_at).total_seconds() * 1000.0, 2)
                if dur < 0:
                    dur = None

            items.append(
                RecentActivityItem(
                    id=row.id,
                    document_id=row.document_id,
                    document_filename=row.original_filename,
                    stage=row.stage,
                    status=row.status,
                    message=row.message,
                    started_at=row.started_at,
                    completed_at=row.completed_at,
                    duration_ms=dur,
                )
            )

        return RecentActivityResponse(items=items, total=len(items))
