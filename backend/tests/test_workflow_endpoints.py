"""
tests/test_workflow_endpoints.py
================================
Tests for Temporal workflow API endpoints:
- POST /api/v1/documents/{id}/process
- GET  /api/v1/documents/{id}/workflow
"""

from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DocumentStatus
from app.models.document import Document


@pytest.mark.asyncio
async def test_start_processing_workflow_success(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="test_proc.pdf",
        stored_filename="test_proc.pdf",
        file_path="storage/test_proc.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.UPLOADED.value,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    response = await async_client.post(f"/api/v1/documents/{doc.id}/process")
    assert response.status_code == 202
    data = response.json()

    assert data["document_id"] == str(doc.id)
    assert data["workflow_id"] == f"document-processing-{doc.id}"
    assert data["run_id"] is not None
    assert data["status"] == DocumentStatus.PROCESSING.value

    # Verify DB update
    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.PROCESSING.value


@pytest.mark.asyncio
async def test_start_processing_workflow_not_found(
    async_client: AsyncClient,
):
    random_id = uuid.uuid4()
    response = await async_client.post(f"/api/v1/documents/{random_id}/process")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_workflow_status_success(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="status_test.pdf",
        stored_filename="status_test.pdf",
        file_path="storage/status_test.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.UPLOADED.value,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # Start workflow first
    start_res = await async_client.post(f"/api/v1/documents/{doc.id}/process")
    assert start_res.status_code == 202

    # Query status
    status_res = await async_client.get(f"/api/v1/documents/{doc.id}/workflow")
    assert status_res.status_code == 200
    data = status_res.json()

    assert data["document_id"] == str(doc.id)
    assert data["workflow_id"] == f"document-processing-{doc.id}"
    assert data["workflow_status"] is not None
    assert data["document_status"] == DocumentStatus.PROCESSING.value


@pytest.mark.asyncio
async def test_get_workflow_status_not_found(
    async_client: AsyncClient,
):
    random_id = uuid.uuid4()
    response = await async_client.get(f"/api/v1/documents/{random_id}/workflow")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_direct_fallback_pipeline_execution(
    async_client: AsyncClient,
    tmp_storage_dir: str,
    mock_ocr,
    fake_llm,
):
    """
    Verify that when Temporal is in fallback/mock mode, POST /documents/{id}/process
    executes the full direct background pipeline on an uploaded file.
    """
    import io
    from app.activities.document_activities import set_activity_providers
    from app.api.v1.endpoints.workflows import _active_direct_tasks
    from app.services.storage.local import LocalStorageProvider
    from app.services.temporal.client import TemporalClientService, get_temporal_client, set_temporal_client

    # Save original temporal client and install mock client
    orig_client = await get_temporal_client()
    mock_temporal = TemporalClientService(client=None, is_mock=True)
    set_temporal_client(mock_temporal)

    try:
        storage = LocalStorageProvider(storage_root=tmp_storage_dir)
        set_activity_providers(storage=storage, ocr=mock_ocr, llm=fake_llm)

        # 1. Upload valid document
        file_bytes = b"%PDF-1.4 direct fallback test invoice"
        files = {"file": ("direct_fallback.pdf", io.BytesIO(file_bytes), "application/pdf")}
        upload_res = await async_client.post("/api/v1/documents", files=files)
        assert upload_res.status_code == 201
        doc_id = upload_res.json()["id"]

        # 2. Trigger processing via POST /process (returns 202 Accepted)
        proc_res = await async_client.post(f"/api/v1/documents/{doc_id}/process")
        assert proc_res.status_code == 202
        proc_data = proc_res.json()
        assert proc_data["document_id"] == doc_id
        assert proc_data["workflow_id"] == f"document-processing-{doc_id}"
        assert proc_data["status"] == DocumentStatus.PROCESSING.value

        # 3. Wait for direct pipeline background task to finish
        task = _active_direct_tasks.get(doc_id)
        if task:
            await task

        # 4. Verify document successfully reached completed/approved status
        status_res = await async_client.get(f"/api/v1/documents/{doc_id}/processing-status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["status"] in (DocumentStatus.APPROVED.value, DocumentStatus.REVIEW_REQUIRED.value)
        assert status_data["workflow_id"] == f"document-processing-{doc_id}"
    finally:
        set_temporal_client(orig_client)


@pytest.mark.asyncio
async def test_direct_fallback_pipeline_failure_handling(
    async_client: AsyncClient,
    tmp_storage_dir: str,
    mock_ocr,
    fake_llm,
):
    """
    Verify that if a stage in the direct pipeline fails, the document transitions
    to FAILED status and is not left indefinitely in PROCESSING.
    """
    import io
    from app.activities.document_activities import set_activity_providers
    from app.api.v1.endpoints.workflows import _active_direct_tasks
    from app.services.storage.local import LocalStorageProvider
    from app.services.temporal.client import TemporalClientService, get_temporal_client, set_temporal_client

    orig_client = await get_temporal_client()
    mock_temporal = TemporalClientService(client=None, is_mock=True)
    set_temporal_client(mock_temporal)

    try:
        mock_ocr.should_fail = True
        storage = LocalStorageProvider(storage_root=tmp_storage_dir)
        set_activity_providers(storage=storage, ocr=mock_ocr, llm=fake_llm)

        # Upload document
        file_bytes = b"%PDF-1.4 failing test invoice"
        files = {"file": ("failing_doc.pdf", io.BytesIO(file_bytes), "application/pdf")}
        upload_res = await async_client.post("/api/v1/documents", files=files)
        assert upload_res.status_code == 201
        doc_id = upload_res.json()["id"]

        # Trigger processing
        proc_res = await async_client.post(f"/api/v1/documents/{doc_id}/process")
        assert proc_res.status_code == 202

        # Await task
        task = _active_direct_tasks.get(doc_id)
        if task:
            await task

        # Check status is FAILED
        status_res = await async_client.get(f"/api/v1/documents/{doc_id}/processing-status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["status"] == DocumentStatus.FAILED.value
        assert status_data["failed_stage"] in ("OCR", "FAILED")
        assert status_data["error_message"] is not None
    finally:
        set_temporal_client(orig_client)
