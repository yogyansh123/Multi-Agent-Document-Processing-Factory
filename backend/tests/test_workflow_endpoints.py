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
