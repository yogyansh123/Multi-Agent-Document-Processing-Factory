"""
tests/test_review.py
====================
Comprehensive tests for Step 8: Human-in-the-Loop Review System.

Covers:
1. Review creation when confidence == REVIEW_REQUIRED
2. No review creation for AUTO_APPROVE
3. Review queue pagination
4. Review queue filtering (status, document_type)
5. Review details endpoint
6. Review details not found (404)
7. Start review lifecycle (PENDING -> IN_REVIEW)
8. Invalid state transitions (COMPLETED -> IN_REVIEW)
9. Approve review flow (Document -> APPROVED, Review -> COMPLETED)
10. Reject review flow (Document -> REJECTED, Review -> COMPLETED)
11. Double-completion prevention (Approve/Reject already completed review)
12. Correct review with schema validation and deterministic revalidation
13. Correction schema validation rejection (invalid data structure)
14. Correction deterministic revalidation with remaining arithmetic issues
15. Duplicate active review prevention
16. Ineligible review creation prevention (recommendation != REVIEW_REQUIRED)
17. Transaction rollback on failure
18. Processing-status review integration (review_id and review_status exposed)
19. Redis cache invalidation on review actions
20. Preservation of original AI extraction vs reviewed extraction
21. Review queue default behavior (PENDING reviews only)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

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
    ReviewDecision,
    ReviewStatus,
    StageStatus,
)
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from app.models.review import DocumentReview
from app.services.cache import RedisService
from app.services.review_service import (
    DocumentNotEligibleForReviewError,
    DuplicateReviewError,
    InvalidReviewStateError,
    ReviewNotFoundError,
    ReviewService,
    ReviewValidationError,
)


# Helper to seed a test document
async def create_test_document(
    db: AsyncSession,
    status: str = DocumentStatus.REVIEW_REQUIRED.value,
    confidence_rec: str = ConfidenceRecommendation.REVIEW_REQUIRED.value,
    overall_confidence: float = 0.65,
    doc_type: str = DocumentType.INVOICE.value,
    extracted_data: dict | None = None,
    validation_score: float = 0.5,
    validation_result: dict | None = None,
) -> Document:
    doc = Document(
        original_filename="test_invoice.pdf",
        stored_filename="test_invoice.pdf",
        file_path="storage/test_invoice.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=2048,
        status=status,
        ocr_text="Invoice #INV-999\nTotal: $500.00\nLine item: Widget $500.00",
        document_type=doc_type,
        classification_confidence=0.95,
        extracted_data=extracted_data or {
            "invoice_number": "INV-999",
            "invoice_date": "2026-03-01",
            "vendor": {"name": "Test Vendor LLC"},
            "total_amount": 500.0,
            "line_items": [{"description": "Widget", "quantity": 1, "unit_price": 500.0, "amount": 500.0}],
        },
        validation_score=validation_score,
        validation_result=validation_result or {
            "is_valid": False,
            "issues": [
                {
                    "code": "MISSING_DUE_DATE",
                    "field": "due_date",
                    "message": "Due date missing",
                    "severity": "WARNING",
                }
            ],
            "rules_checked": ["INV_REQUIRED_FIELDS"],
        },
        overall_confidence=overall_confidence,
        confidence_recommendation=confidence_rec,
        confidence_factors={"weights": {"classification": 0.25, "extraction": 0.35, "validation": 0.40}},
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@pytest.mark.asyncio
async def test_review_creation_when_confidence_review_required(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 1: Review is automatically created when ConfidenceService evaluates REVIEW_REQUIRED."""
    doc = Document(
        original_filename="low_conf_invoice.pdf",
        stored_filename="low_conf_invoice.pdf",
        file_path="storage/low_conf_invoice.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1024,
        status=DocumentStatus.VALIDATED.value,
        ocr_text="Invoice low confidence",
        document_type=DocumentType.INVOICE.value,
        classification_confidence=0.50,
        extracted_data={"invoice_number": "INV-1"},
        validation_result={"is_valid": False, "issues": [{"severity": "ERROR", "message": "Failed"}]},
        validation_score=0.40,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    res = await async_client.post(f"/api/v1/documents/{doc.id}/confidence")
    assert res.status_code == 200
    assert res.json()["recommendation"] == ConfidenceRecommendation.REVIEW_REQUIRED.value

    # Verify DocumentReview record was created
    stmt = select(DocumentReview).where(DocumentReview.document_id == doc.id)
    review_res = await db_session.execute(stmt)
    review = review_res.scalar_one_or_none()

    assert review is not None
    assert review.status == ReviewStatus.PENDING.value
    assert review.decision is None
    assert review.document_id == doc.id
    assert review.original_extracted_data == {"invoice_number": "INV-1"}


@pytest.mark.asyncio
async def test_no_review_creation_for_auto_approve(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 2: No review record created when confidence scores AUTO_APPROVE."""
    doc = Document(
        original_filename="perfect_invoice.pdf",
        stored_filename="perfect_invoice.pdf",
        file_path="storage/perfect_invoice.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1024,
        status=DocumentStatus.VALIDATED.value,
        ocr_text="Perfect invoice text",
        document_type=DocumentType.INVOICE.value,
        classification_confidence=0.99,
        extracted_data={
            "invoice_number": "INV-100",
            "invoice_date": "2026-01-01",
            "vendor": {"name": "Vendor"},
            "total_amount": 100.0,
            "line_items": [{"description": "Item", "amount": 100.0}],
        },
        validation_result={"is_valid": True, "issues": []},
        validation_score=1.0,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    res = await async_client.post(f"/api/v1/documents/{doc.id}/confidence")
    assert res.status_code == 200
    assert res.json()["recommendation"] == ConfidenceRecommendation.AUTO_APPROVE.value

    # Verify NO DocumentReview record exists
    stmt = select(DocumentReview).where(DocumentReview.document_id == doc.id)
    review_res = await db_session.execute(stmt)
    assert review_res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_review_queue_pagination(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 3: Review queue pagination works correctly."""
    service = ReviewService(db=db_session)
    for i in range(5):
        doc = await create_test_document(db_session)
        doc.original_filename = f"doc_{i}.pdf"
        await db_session.commit()
        await service.create_review(doc.id)

    # Request page 1 with page_size 2
    res = await async_client.get("/api/v1/review/queue?page=1&page_size=2")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total"] >= 5
    assert data["total_pages"] >= 3


@pytest.mark.asyncio
async def test_review_queue_filtering(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 4: Review queue filters by status and document_type."""
    service = ReviewService(db=db_session)

    # 1 Invoice, 1 Receipt
    doc_inv = await create_test_document(db_session, doc_type="INVOICE")
    doc_rec = await create_test_document(db_session, doc_type="RECEIPT")

    rev_inv = await service.create_review(doc_inv.id)
    rev_rec = await service.create_review(doc_rec.id)

    # Start invoice review so it is IN_REVIEW
    await service.start_review(rev_inv.id)

    # Filter by status=IN_REVIEW
    res_status = await async_client.get("/api/v1/review/queue?status=IN_REVIEW")
    assert res_status.status_code == 200
    items = res_status.json()["items"]
    assert all(it["status"] == "IN_REVIEW" for it in items)
    assert any(it["review_id"] == str(rev_inv.id) for it in items)

    # Filter by document_type=RECEIPT
    res_type = await async_client.get("/api/v1/review/queue?document_type=RECEIPT&status=ALL")
    assert res_type.status_code == 200
    type_items = res_type.json()["items"]
    assert all(it["document_type"] == "RECEIPT" for it in type_items)
    assert any(it["review_id"] == str(rev_rec.id) for it in type_items)


@pytest.mark.asyncio
async def test_review_details_endpoint(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 5 & 6: Review details retrieval and 404 handling."""
    doc = await create_test_document(db_session)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)

    res = await async_client.get(f"/api/v1/review/{review.id}")
    assert res.status_code == 200
    data = res.json()

    assert data["review_id"] == str(review.id)
    assert data["document_id"] == str(doc.id)
    assert data["status"] == "PENDING"
    assert data["document"]["original_filename"] == doc.original_filename
    assert data["document"]["ocr_text"] == doc.ocr_text
    assert data["original_extracted_data"] is not None
    assert data["confidence_snapshot"] is not None

    # Test 404 for nonexistent review
    res_404 = await async_client.get(f"/api/v1/review/{uuid.uuid4()}")
    assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_start_review_lifecycle(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 7: Start review transitions from PENDING to IN_REVIEW."""
    doc = await create_test_document(db_session)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)

    res = await async_client.post(
        f"/api/v1/review/{review.id}/start",
        json={"reviewer_name": "Alice Auditor"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "IN_REVIEW"

    # Verify DB state
    await db_session.refresh(review)
    assert review.status == "IN_REVIEW"
    assert review.reviewer_name == "Alice Auditor"


@pytest.mark.asyncio
async def test_invalid_state_transition(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 8: Prevent starting an already COMPLETED review."""
    doc = await create_test_document(db_session)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)

    # Approve review first
    await service.approve_review(review.id, reason="Done")

    # Attempt to start review now
    res = await async_client.post(f"/api/v1/review/{review.id}/start")
    assert res.status_code == 400
    assert "already COMPLETED" in res.json()["detail"]


@pytest.mark.asyncio
async def test_approve_review_flow(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 9: Approve review transitions Document to APPROVED and Review to COMPLETED."""
    doc = await create_test_document(db_session)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)

    res = await async_client.post(
        f"/api/v1/review/{review.id}/approve",
        json={"reason": "Extraction verified manually", "reviewer_name": "Bob"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["decision"] == "APPROVED"
    assert data["document_status"] == "APPROVED"

    # Verify Document state in DB
    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.APPROVED.value

    # Verify ProcessingHistory entry
    stmt = select(ProcessingHistory).where(
        ProcessingHistory.document_id == doc.id,
        ProcessingHistory.stage == ProcessingStage.HUMAN_REVIEW.value,
    )
    hist_res = await db_session.execute(stmt)
    hist = hist_res.scalars().all()
    assert len(hist) > 0
    assert hist[-1].status == StageStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_reject_review_flow(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 10: Reject review transitions Document to REJECTED."""
    doc = await create_test_document(db_session)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)

    res = await async_client.post(
        f"/api/v1/review/{review.id}/reject",
        json={"reason": "Corrupted invoice details", "reviewer_name": "Charlie"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["decision"] == "REJECTED"
    assert data["document_status"] == "REJECTED"

    # Verify Document state in DB
    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.REJECTED.value


@pytest.mark.asyncio
async def test_prevent_double_completion(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 11: Attempting to approve/reject an already completed review fails."""
    doc = await create_test_document(db_session)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)

    # First approve
    await service.approve_review(review.id)

    # Second approve should fail
    res_app = await async_client.post(f"/api/v1/review/{review.id}/approve")
    assert res_app.status_code == 400

    # Reject on completed review should fail
    res_rej = await async_client.post(f"/api/v1/review/{review.id}/reject")
    assert res_rej.status_code == 400


@pytest.mark.asyncio
async def test_correct_review_valid_flow(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 12: Correct extraction validates schema, re-validates, and approves document."""
    # Document with arithmetic mismatch in line item
    extracted = {
        "invoice_number": "INV-101",
        "invoice_date": "2026-03-01",
        "vendor": {"name": "Valid Vendor"},
        "total_amount": 100.0,
        "line_items": [{"description": "Item A", "quantity": 2, "unit_price": 40.0, "amount": 100.0}],  # 2*40 != 100
    }
    doc = await create_test_document(db_session, extracted_data=extracted)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)

    # Submit corrected line item (2 * 50 = 100)
    corrected = {
        "invoice_number": "INV-101",
        "invoice_date": "2026-03-01",
        "vendor": {"name": "Valid Vendor"},
        "total_amount": 100.0,
        "line_items": [{"description": "Item A", "quantity": 2, "unit_price": 50.0, "amount": 100.0}],
    }

    res = await async_client.post(
        f"/api/v1/review/{review.id}/correct",
        json={"corrected_data": corrected, "reason": "Fixed unit price", "reviewer_name": "Auditor"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["decision"] == "CORRECTED"
    assert data["document_status"] == "APPROVED"

    # Verify DB state
    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.APPROVED.value
    assert doc.extracted_data["line_items"][0]["unit_price"] == 50.0

    await db_session.refresh(review)
    assert review.reviewed_extracted_data is not None
    assert review.original_extracted_data["line_items"][0]["unit_price"] == 40.0


@pytest.mark.asyncio
async def test_correct_review_invalid_schema(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 13: Schema validation failure returns 400 Bad Request."""
    doc = await create_test_document(db_session)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)

    # Invoice expects total_amount as float/number, provide invalid type
    invalid_data = {
        "invoice_number": 12345,  # Validates to string or ok
        "total_amount": "not-a-number",  # Invalid float
    }

    res = await async_client.post(
        f"/api/v1/review/{review.id}/correct",
        json={"corrected_data": invalid_data},
    )
    assert res.status_code == 400
    assert "schema validation" in res.json()["detail"]


@pytest.mark.asyncio
async def test_correct_review_deterministic_revalidation_with_error(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 14: Corrected data that still violates deterministic rules stays in REVIEW_REQUIRED."""
    doc = await create_test_document(db_session)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)

    # Correction still has line item arithmetic mismatch
    corrected = {
        "invoice_number": "INV-102",
        "vendor": {"name": "Vendor"},
        "total_amount": 200.0,
        "line_items": [{"description": "Item", "quantity": 1, "unit_price": 50.0, "amount": 200.0}],
    }

    res = await async_client.post(
        f"/api/v1/review/{review.id}/correct",
        json={"corrected_data": corrected},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "CORRECTED"
    # Still has errors, so document remains REVIEW_REQUIRED
    assert data["document_status"] == DocumentStatus.REVIEW_REQUIRED.value


@pytest.mark.asyncio
async def test_duplicate_active_review_prevention(
    db_session: AsyncSession,
):
    """Test 15: Creating duplicate active review for the same document raises DuplicateReviewError."""
    doc = await create_test_document(db_session)
    service = ReviewService(db=db_session)

    # First review succeeds
    await service.create_review(doc.id)

    # Second active review raises DuplicateReviewError
    with pytest.raises(DuplicateReviewError):
        await service.create_review(doc.id)


@pytest.mark.asyncio
async def test_ineligible_review_creation_prevention(
    db_session: AsyncSession,
):
    """Test 16: Attempting to create review for AUTO_APPROVE document raises DocumentNotEligibleForReviewError."""
    doc = await create_test_document(
        db_session,
        confidence_rec=ConfidenceRecommendation.AUTO_APPROVE.value,
        status=DocumentStatus.APPROVED.value,
    )
    service = ReviewService(db=db_session)

    with pytest.raises(DocumentNotEligibleForReviewError):
        await service.create_review(doc.id)


@pytest.mark.asyncio
async def test_transaction_rollback_on_failure(
    db_session: AsyncSession,
):
    """Test 17: Database error during review operation rolls back cleanly."""
    doc = await create_test_document(db_session)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)
    review_id = review.id

    # Patch commit to simulate a DB connection drop
    with patch.object(db_session, "commit", side_effect=RuntimeError("Simulated DB connection failure")):
        with pytest.raises(RuntimeError, match="Simulated DB connection failure"):
            await service.approve_review(review_id)

    # Reload review from clean query, status must still be PENDING
    fresh_review = await service.get_review(review_id)
    assert fresh_review.status == ReviewStatus.PENDING.value
    assert fresh_review.decision is None



@pytest.mark.asyncio
async def test_processing_status_review_integration(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 18: GET /processing-status exposes review_id and review_status."""
    doc = await create_test_document(db_session)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)

    res = await async_client.get(f"/api/v1/documents/{doc.id}/processing-status")
    assert res.status_code == 200
    data = res.json()

    assert data["document_id"] == str(doc.id)
    assert data["status"] == DocumentStatus.REVIEW_REQUIRED.value
    assert data["review_id"] == str(review.id)
    assert data["review_status"] == ReviewStatus.PENDING.value


@pytest.mark.asyncio
async def test_redis_cache_invalidation_on_review_actions(
    db_session: AsyncSession,
):
    """Test 19: Review lifecycle operations invalidate Redis status cache."""
    mock_redis = AsyncMock(spec=RedisService)
    service = ReviewService(db=db_session, redis_service=mock_redis)

    doc = await create_test_document(db_session)
    review = await service.create_review(doc.id)

    # Test approve invalidation
    await service.approve_review(review.id)
    mock_redis.delete_document_status.assert_called_with(doc.id)


@pytest.mark.asyncio
async def test_preservation_of_original_ai_extraction(
    db_session: AsyncSession,
):
    """Test 20: Original AI extraction is preserved when human corrections are made."""
    original = {"invoice_number": "ORIG-100", "total_amount": 10.0}
    doc = await create_test_document(db_session, extracted_data=original)
    service = ReviewService(db=db_session)
    review = await service.create_review(doc.id)

    corrected = {"invoice_number": "CORRECTED-200", "total_amount": 20.0}
    await service.correct_review(review.id, corrected_data=corrected)

    await db_session.refresh(review)
    assert review.original_extracted_data["invoice_number"] == "ORIG-100"
    assert review.reviewed_extracted_data["invoice_number"] == "CORRECTED-200"


@pytest.mark.asyncio
async def test_review_queue_default_pending_only(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 21: Review queue by default returns only PENDING reviews."""
    service = ReviewService(db=db_session)
    doc1 = await create_test_document(db_session)
    doc2 = await create_test_document(db_session)

    rev1 = await service.create_review(doc1.id)
    rev2 = await service.create_review(doc2.id)

    # Approve rev2 so it becomes COMPLETED
    await service.approve_review(rev2.id)

    # Default queue query
    res = await async_client.get("/api/v1/review/queue")
    assert res.status_code == 200
    items = res.json()["items"]

    # rev1 should be present, rev2 should NOT be in default pending queue
    rev_ids = [it["review_id"] for it in items]
    assert str(rev1.id) in rev_ids
    assert str(rev2.id) not in rev_ids
