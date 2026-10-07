"""
tests/test_confidence.py
========================
Tests for Step 6: Confidence Scoring and Auto Approval / Review Required routing.

Deterministic, zero-external-API tests using FakeLLMProvider and in-memory SQLite.
"""

from __future__ import annotations

import io
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import (
    ConfidenceRecommendation,
    DocumentStatus,
    DocumentType,
    ProcessingStage,
    StageStatus,
)
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.services.confidence_service import (
    compute_extraction_completeness,
)


# ---------------------------------------------------------------------------
# Unit Tests: Extraction Completeness & Formula
# ---------------------------------------------------------------------------


def test_extraction_completeness_calculation():
    # Fully populated invoice
    invoice_data = {
        "invoice_number": "INV-001",
        "invoice_date": "2026-01-01",
        "vendor": {"name": "Vendor"},
        "total_amount": 100.0,
        "line_items": [{"description": "Item 1", "amount": 100.0}],
    }
    score = compute_extraction_completeness("INVOICE", invoice_data)
    assert score == 1.0

    # Partially populated invoice (3 out of 5)
    partial_invoice = {
        "invoice_number": "INV-001",
        "vendor": {"name": "Vendor"},
        "total_amount": 100.0,
    }
    partial_score = compute_extraction_completeness("INVOICE", partial_invoice)
    assert partial_score == 0.6

    # Empty
    assert compute_extraction_completeness("INVOICE", {}) == 0.0
    assert compute_extraction_completeness("INVOICE", None) == 0.0


# ---------------------------------------------------------------------------
# API Endpoint Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confidence_scoring_auto_approval_flow(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="clean_invoice.pdf",
        stored_filename="clean_invoice.pdf",
        file_path="storage/clean_invoice.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.VALIDATED.value,
        ocr_text="Clean Invoice Text",
        document_type=DocumentType.INVOICE.value,
        classification_confidence=0.98,
        extracted_data={
            "invoice_number": "INV-100",
            "invoice_date": "2026-01-01",
            "vendor": {"name": "Acme Inc"},
            "total_amount": 100.0,
            "line_items": [{"description": "Item 1", "amount": 100.0}],
        },
        validation_result={"is_valid": True, "issues": []},
        validation_score=1.0,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    response = await async_client.post(f"/api/v1/documents/{doc.id}/confidence")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == str(doc.id)
    assert data["recommendation"] == ConfidenceRecommendation.AUTO_APPROVE.value
    assert data["status"] == DocumentStatus.APPROVED.value
    assert data["overall_confidence"] >= settings.AUTO_APPROVAL_THRESHOLD
    assert "weights" in data["confidence_factors"]

    # Verify DB update
    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.APPROVED.value
    assert doc.confidence_recommendation == ConfidenceRecommendation.AUTO_APPROVE.value


@pytest.mark.asyncio
async def test_confidence_scoring_review_required_due_to_validation_errors(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="error_invoice.pdf",
        stored_filename="error_invoice.pdf",
        file_path="storage/error_invoice.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.VALIDATED.value,
        ocr_text="Invoice with errors",
        document_type=DocumentType.INVOICE.value,
        classification_confidence=0.95,
        extracted_data={
            "invoice_number": "INV-200",
            "vendor": {"name": "Acme Inc"},
        },
        validation_result={
            "is_valid": False,
            "issues": [
                {
                    "code": "MISSING_TOTAL_AMOUNT",
                    "field": "total_amount",
                    "message": "Missing total",
                    "severity": "ERROR",
                }
            ],
        },
        validation_score=0.45,
    )
    db_session.add(doc)
    await db_session.commit()

    response = await async_client.post(f"/api/v1/documents/{doc.id}/confidence")
    assert response.status_code == 200
    data = response.json()

    assert data["recommendation"] == ConfidenceRecommendation.REVIEW_REQUIRED.value
    assert data["status"] == DocumentStatus.REVIEW_REQUIRED.value


@pytest.mark.asyncio
async def test_confidence_before_validation_returns_409(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="not_validated.pdf",
        stored_filename="not_validated.pdf",
        file_path="storage/not_validated.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.EXTRACTED.value,
        document_type="INVOICE",
        validation_result=None,
    )
    db_session.add(doc)
    await db_session.commit()

    response = await async_client.post(f"/api/v1/documents/{doc.id}/confidence")
    assert response.status_code == 409
    assert "validation has not completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_confidence_nonexistent_document_returns_404(
    async_client: AsyncClient,
):
    response = await async_client.post(f"/api/v1/documents/{uuid.uuid4()}/confidence")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_confidence_before_and_after_scoring(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="test_doc.pdf",
        stored_filename="test_doc.pdf",
        file_path="storage/test_doc.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.VALIDATED.value,
        document_type="INVOICE",
        classification_confidence=0.90,
        extracted_data={"invoice_number": "INV-1"},
        validation_result={"is_valid": True, "issues": []},
        validation_score=0.90,
    )
    db_session.add(doc)
    await db_session.commit()

    # Before scoring -> 409
    res1 = await async_client.get(f"/api/v1/documents/{doc.id}/confidence")
    assert res1.status_code == 409

    # Score confidence
    res2 = await async_client.post(f"/api/v1/documents/{doc.id}/confidence")
    assert res2.status_code == 200

    # After scoring -> 200
    res3 = await async_client.get(f"/api/v1/documents/{doc.id}/confidence")
    assert res3.status_code == 200
    assert res3.json()["overall_confidence"] > 0.0


# ---------------------------------------------------------------------------
# Full End-to-End Pipeline Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_document_processing_pipeline_to_approval(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Test complete lifecycle from Upload through Auto-Approval:
    Upload -> OCR -> Classify -> Extract -> Validate -> Confidence -> Auto-Approve
    """
    # 1. Upload
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<\n/Title (Invoice INV-9001)\n>>\nendobj\ntrailer\n<<\n>>\n%%EOF"
    upload_res = await async_client.post(
        "/api/v1/documents",
        files={"file": ("invoice_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. OCR
    ocr_res = await async_client.post(f"/api/v1/documents/{doc_id}/ocr")
    assert ocr_res.status_code == 200
    assert ocr_res.json()["status"] == DocumentStatus.OCR_COMPLETED.value

    # 3. Classify
    classify_res = await async_client.post(f"/api/v1/documents/{doc_id}/classify")
    assert classify_res.status_code == 200
    assert classify_res.json()["document_type"] == "INVOICE"
    assert classify_res.json()["status"] == DocumentStatus.CLASSIFIED.value

    # 4. Extract
    extract_res = await async_client.post(f"/api/v1/documents/{doc_id}/extract")
    assert extract_res.status_code == 200
    assert extract_res.json()["status"] == DocumentStatus.EXTRACTED.value

    # 5. Validate
    validate_res = await async_client.post(f"/api/v1/documents/{doc_id}/validate")
    assert validate_res.status_code == 200
    assert validate_res.json()["status"] == DocumentStatus.VALIDATED.value

    # 6. Confidence Scoring
    confidence_res = await async_client.post(f"/api/v1/documents/{doc_id}/confidence")
    assert confidence_res.status_code == 200
    final_status = confidence_res.json()["status"]
    assert final_status in (DocumentStatus.APPROVED.value, DocumentStatus.REVIEW_REQUIRED.value)

    # Verify history records for all stages exist
    hist_result = await db_session.execute(
        select(ProcessingHistory).where(ProcessingHistory.document_id == uuid.UUID(doc_id))
    )
    histories = hist_result.scalars().all()
    stages = [h.stage for h in histories]

    assert ProcessingStage.UPLOAD.value in stages
    assert ProcessingStage.OCR.value in stages
    assert ProcessingStage.CLASSIFICATION.value in stages
    assert ProcessingStage.EXTRACTION.value in stages
    assert ProcessingStage.VALIDATION.value in stages
    assert ProcessingStage.CONFIDENCE_SCORING.value in stages

    for h in histories:
        assert h.status == StageStatus.COMPLETED.value
