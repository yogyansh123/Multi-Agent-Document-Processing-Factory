"""
tests/test_processing_status.py
================================
Tests for GET /api/v1/documents/{document_id}/processing-status:
- Cached status
- Uncached status (reads from PostgreSQL, writes to Redis)
- Document not found (404)
- Active workflow
- Completed workflow
- Failed workflow
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DocumentStatus, ProcessingStage, StageStatus
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.services.cache import get_redis_service


@pytest.mark.asyncio
async def test_get_processing_status_not_found(async_client: AsyncClient):
    """Querying an unknown document returns 404."""
    random_id = uuid.uuid4()
    response = await async_client.get(f"/api/v1/documents/{random_id}/processing-status")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_processing_status_uncached_and_caches_result(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    On cache miss, reads from PostgreSQL, returns valid status,
    and updates the Redis cache.
    """
    doc = Document(
        original_filename="invoice_status.pdf",
        stored_filename="invoice_status.pdf",
        file_path="storage/invoice_status.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=2048,
        status=DocumentStatus.UPLOADED.value,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    response = await async_client.get(f"/api/v1/documents/{doc.id}/processing-status")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == str(doc.id)
    assert data["status"] == DocumentStatus.UPLOADED.value
    assert data["current_stage"] == "UPLOAD"
    assert data["workflow_id"] == f"document-processing-{doc.id}"

    # Verify that the value was written into Redis cache
    redis_service = await get_redis_service()
    cached = await redis_service.get_document_status(doc.id)
    assert cached is not None
    assert cached["document_id"] == str(doc.id)
    assert cached["status"] == DocumentStatus.UPLOADED.value


@pytest.mark.asyncio
async def test_get_processing_status_from_cache(
    async_client: AsyncClient,
):
    """
    When Redis has cached status, the endpoint returns the cached data immediately.
    """
    doc_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    cached_payload = {
        "document_id": str(doc_id),
        "status": "APPROVED",
        "current_stage": "CONFIDENCE_SCORING",
        "workflow_id": f"document-processing-{doc_id}",
        "overall_confidence": 0.98,
        "confidence_recommendation": "APPROVED",
        "started_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "completed_at": now.isoformat(),
        "failed_stage": None,
        "error_message": None,
    }

    redis_service = await get_redis_service()
    await redis_service.set_document_status(doc_id, cached_payload)

    # Note that doc_id does NOT exist in PostgreSQL — returning 200 proves Redis cache hit!
    response = await async_client.get(f"/api/v1/documents/{doc_id}/processing-status")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == str(doc_id)
    assert data["status"] == "APPROVED"
    assert data["overall_confidence"] == 0.98
    assert data["confidence_recommendation"] == "APPROVED"


@pytest.mark.asyncio
async def test_get_processing_status_active_workflow(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    When a document is in PROCESSING status, queries live workflow state.
    """
    doc = Document(
        original_filename="active_proc.pdf",
        stored_filename="active_proc.pdf",
        file_path="storage/active_proc.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1024,
        status=DocumentStatus.UPLOADED.value,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # Start the workflow
    start_res = await async_client.post(f"/api/v1/documents/{doc.id}/process")
    assert start_res.status_code == 202

    # Query processing status
    response = await async_client.get(f"/api/v1/documents/{doc.id}/processing-status")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == str(doc.id)
    assert data["status"] == DocumentStatus.PROCESSING.value
    assert data["workflow_id"] == f"document-processing-{doc.id}"
    assert data["current_stage"] in ("INITIALIZED", "PROCESSING", "OCR")


@pytest.mark.asyncio
async def test_get_processing_status_completed_workflow(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies completed workflow mapping to confidence metrics and completed_at timestamp.
    """
    now = datetime.now(timezone.utc)
    doc = Document(
        original_filename="completed_doc.pdf",
        stored_filename="completed_doc.pdf",
        file_path="storage/completed_doc.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=2048,
        status=DocumentStatus.APPROVED.value,
        overall_confidence=0.92,
        confidence_recommendation="APPROVED",
    )
    db_session.add(doc)
    await db_session.flush()

    history = ProcessingHistory(
        document_id=doc.id,
        stage=ProcessingStage.CONFIDENCE_SCORING.value,
        status=StageStatus.COMPLETED.value,
        started_at=now,
        completed_at=now,
        message="Auto-approved",
    )
    db_session.add(history)
    await db_session.commit()
    await db_session.refresh(doc)

    # Clear cache first to ensure PostgreSQL read
    redis_service = await get_redis_service()
    await redis_service.delete_document_status(doc.id)

    response = await async_client.get(f"/api/v1/documents/{doc.id}/processing-status")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == str(doc.id)
    assert data["status"] == "APPROVED"
    assert data["current_stage"] == "CONFIDENCE_SCORING"
    assert data["overall_confidence"] == 0.92
    assert data["confidence_recommendation"] == "APPROVED"
    assert data["completed_at"] is not None


@pytest.mark.asyncio
async def test_get_processing_status_failed_workflow(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies failed workflow mapping to failed_stage and error_message.
    """
    now = datetime.now(timezone.utc)
    doc = Document(
        original_filename="corrupt.pdf",
        stored_filename="corrupt.pdf",
        file_path="storage/corrupt.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=500,
        status=DocumentStatus.FAILED.value,
        error_message="OCR unreadable corrupt stream",
    )
    db_session.add(doc)
    await db_session.flush()

    history = ProcessingHistory(
        document_id=doc.id,
        stage=ProcessingStage.OCR.value,
        status=StageStatus.FAILED.value,
        started_at=now,
        completed_at=now,
        message="OCR failed on corrupt stream",
    )
    db_session.add(history)
    await db_session.commit()

    redis_service = await get_redis_service()
    await redis_service.delete_document_status(doc.id)

    response = await async_client.get(f"/api/v1/documents/{doc.id}/processing-status")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == str(doc.id)
    assert data["status"] == "FAILED"
    assert data["failed_stage"] == "OCR"
    assert data["error_message"] == "OCR unreadable corrupt stream"


@pytest.mark.asyncio
async def test_process_document_invalidates_stale_cache(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Starting a workflow must invalidate any pre-existing cached status in Redis.
    """
    doc = Document(
        original_filename="stale_cached_doc.pdf",
        stored_filename="stale_cached_doc.pdf",
        file_path="storage/stale_cached_doc.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1024,
        status=DocumentStatus.OCR_COMPLETED.value,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # Seed Redis with stale pre-processing status
    redis_service = await get_redis_service()
    await redis_service.set_document_status(
        doc.id,
        {
            "document_id": str(doc.id),
            "status": "OCR_COMPLETED",
            "current_stage": "OCR",
        },
    )

    # Trigger processing
    start_res = await async_client.post(f"/api/v1/documents/{doc.id}/process")
    assert start_res.status_code == 202

    # Cached status must have been invalidated/purged
    cached_after = await redis_service.get_document_status(doc.id)
    assert cached_after is None


@pytest.mark.asyncio
async def test_get_processing_status_bypasses_stale_nonterminal_cache(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    If Redis contains a stale non-terminal status, GET /processing-status
    fetches the durable source of truth (PostgreSQL) and returns terminal status.
    """
    doc = Document(
        original_filename="certificate_review.pdf",
        stored_filename="certificate_review.pdf",
        file_path="storage/certificate_review.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=2048,
        status=DocumentStatus.REVIEW_REQUIRED.value,
        overall_confidence=0.775,
        confidence_recommendation="REVIEW_REQUIRED",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # Seed Redis with stale non-terminal status (e.g. from pre-processing OCR)
    redis_service = await get_redis_service()
    await redis_service.set_document_status(
        doc.id,
        {
            "document_id": str(doc.id),
            "status": "OCR_COMPLETED",
            "current_stage": "OCR",
        },
    )

    # Query processing status
    response = await async_client.get(f"/api/v1/documents/{doc.id}/processing-status")
    assert response.status_code == 200
    data = response.json()

    # Must return the updated terminal status from database, not the stale OCR_COMPLETED
    assert data["status"] == "REVIEW_REQUIRED"
    assert data["overall_confidence"] == 0.775
