"""
tests/test_extraction.py
========================
Comprehensive tests for Step 5: LangGraph Information Extraction Agent.

Test coverage:
1. Invoice schema validation (valid invoice, nullable defaults, line items).
2. Receipt schema validation.
3. Purchase Order schema validation.
4. Contract schema validation.
5. Other / general document schema validation.
6. Schema selection mechanism for all document types.
7. Standalone extraction graph execution for Invoice.
8. Standalone extraction graph execution for Receipt.
9. Standalone extraction graph execution for Purchase Order.
10. Standalone extraction graph execution for Contract.
11. Standalone extraction graph execution for Other.
12. Standalone extraction graph error handling (empty text).
13. Standalone extraction graph error handling (missing classification).
14. Trigger extraction endpoint (POST /api/v1/documents/{id}/extract) success.
15. Database persistence of extracted_data, extraction_version, and extracted_at.
16. ProcessingHistory record creation for stage=EXTRACTION.
17. Extraction before OCR completion returns 409 Conflict.
18. Extraction before Classification completion returns 409 Conflict.
19. Extraction failure flow (LLM error -> status=FAILED, history recorded, 422 response).
20. Extraction 404 for nonexistent document.
21. Get extraction endpoint (GET /api/v1/documents/{id}/extraction) success.
22. Get extraction before extraction returns 409 Conflict.
23. Get extraction 404 for nonexistent document.
24. Re-extraction flow (overwriting data, appending fresh history record).
"""

from __future__ import annotations

import io
import uuid
import pytest
from httpx import AsyncClient

from app.agents.extraction.graph import create_extraction_graph
from app.agents.extraction.schemas import (
    ContactInfo,
    ContractExtraction,
    InvoiceExtraction,
    InvoiceLineItem,
    KeyValueItem,
    OtherExtraction,
    PurchaseOrderExtraction,
    PurchaseOrderLineItem,
    ReceiptExtraction,
    ReceiptItem,
    get_extraction_schema,
)
from app.api.deps import get_llm_provider
from app.core.enums import DocumentStatus, DocumentType, ProcessingStage, StageStatus
from app.main import app as fastapi_app
from tests.conftest import FakeLLMProvider

VALID_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF"
)


# ---------------------------------------------------------------------------
# 1. Schema Validation Tests
# ---------------------------------------------------------------------------

def test_invoice_schema_validation():
    """InvoiceExtraction validates fields, preserves nulls, and serializes."""
    inv = InvoiceExtraction(
        invoice_number="INV-100",
        total=1250.50,
        currency="USD",
        vendor=ContactInfo(name="Vendor A"),
        line_items=[InvoiceLineItem(description="Widget", quantity=2, unit_price=500.0, amount=1000.0)],
    )
    assert inv.invoice_number == "INV-100"
    assert inv.total == 1250.50
    assert inv.due_date is None
    assert inv.discount is None
    assert len(inv.line_items) == 1
    assert inv.vendor.name == "Vendor A"  # type: ignore[union-attr]


def test_receipt_schema_validation():
    """ReceiptExtraction validates fields."""
    rec = ReceiptExtraction(
        receipt_number="R-42",
        merchant="Supermarket",
        total=45.20,
        items=[ReceiptItem(description="Milk", amount=4.50)],
        payment_method="Cash",
    )
    assert rec.merchant == "Supermarket"
    assert rec.total == 45.20
    assert len(rec.items) == 1


def test_purchase_order_schema_validation():
    """PurchaseOrderExtraction validates fields."""
    po = PurchaseOrderExtraction(
        po_number="PO-999",
        buyer=ContactInfo(name="Buyer Corp"),
        total=5000.0,
        line_items=[PurchaseOrderLineItem(description="Laptops", quantity=5, amount=5000.0)],
    )
    assert po.po_number == "PO-999"
    assert po.delivery_date is None


def test_contract_schema_validation():
    """ContractExtraction validates fields."""
    con = ContractExtraction(
        contract_title="Non-Disclosure Agreement",
        parties=["Alice", "Bob"],
        governing_law="California",
    )
    assert con.contract_title == "Non-Disclosure Agreement"
    assert len(con.parties) == 2
    assert con.expiration_date is None


def test_other_schema_validation():
    """OtherExtraction validates fields."""
    oth = OtherExtraction(
        title="Weekly Notes",
        key_values=[KeyValueItem(key="Topic", value="Roadmap")],
        summary="Discussion on Q3 deliverables.",
    )
    assert oth.title == "Weekly Notes"
    assert len(oth.key_values) == 1
    assert oth.document_date is None


def test_schema_selection_mechanism():
    """get_extraction_schema maps every DocumentType correctly."""
    assert get_extraction_schema(DocumentType.INVOICE) == InvoiceExtraction
    assert get_extraction_schema("INVOICE") == InvoiceExtraction
    assert get_extraction_schema(DocumentType.RECEIPT) == ReceiptExtraction
    assert get_extraction_schema(DocumentType.PURCHASE_ORDER) == PurchaseOrderExtraction
    assert get_extraction_schema(DocumentType.CONTRACT) == ContractExtraction
    assert get_extraction_schema(DocumentType.OTHER) == OtherExtraction
    assert get_extraction_schema("UNKNOWN_TYPE") == OtherExtraction


# ---------------------------------------------------------------------------
# 2. Standalone LangGraph Execution Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_standalone_invoice_extraction_graph():
    """Invoice extraction graph executes with FakeLLMProvider."""
    fake_llm = FakeLLMProvider()
    graph = create_extraction_graph(llm_provider=fake_llm, db=None)

    initial_state = {
        "document_text": "Invoice # INV-2026-001\nTotal: $1,650.00",
        "document_type": DocumentType.INVOICE.value,
    }

    result = await graph.ainvoke(initial_state)
    assert result.get("error") is None
    assert result["extracted_data"]["invoice_number"] == "INV-2026-001"
    assert result["extracted_data"]["total"] == 1650.0
    assert result["schema_name"] == "InvoiceExtraction"


@pytest.mark.asyncio
async def test_standalone_receipt_extraction_graph():
    """Receipt extraction graph executes with FakeLLMProvider."""
    fake_llm = FakeLLMProvider()
    graph = create_extraction_graph(llm_provider=fake_llm, db=None)

    initial_state = {
        "document_text": "Coffee Shop Receipt REC-999 Total: $9.90",
        "document_type": DocumentType.RECEIPT.value,
    }

    result = await graph.ainvoke(initial_state)
    assert result.get("error") is None
    assert result["extracted_data"]["merchant"] == "Coffee Shop"
    assert result["schema_name"] == "ReceiptExtraction"


@pytest.mark.asyncio
async def test_standalone_purchase_order_extraction_graph():
    """Purchase Order extraction graph executes with FakeLLMProvider."""
    fake_llm = FakeLLMProvider()
    graph = create_extraction_graph(llm_provider=fake_llm, db=None)

    initial_state = {
        "document_text": "PO-2026-444 Supplies Direct Total: $540.00",
        "document_type": DocumentType.PURCHASE_ORDER.value,
    }

    result = await graph.ainvoke(initial_state)
    assert result.get("error") is None
    assert result["extracted_data"]["po_number"] == "PO-2026-444"
    assert result["schema_name"] == "PurchaseOrderExtraction"


@pytest.mark.asyncio
async def test_standalone_contract_extraction_graph():
    """Contract extraction graph executes with FakeLLMProvider."""
    fake_llm = FakeLLMProvider()
    graph = create_extraction_graph(llm_provider=fake_llm, db=None)

    initial_state = {
        "document_text": "Master Services Agreement between Acme Corp and Beta LLC",
        "document_type": DocumentType.CONTRACT.value,
    }

    result = await graph.ainvoke(initial_state)
    assert result.get("error") is None
    assert result["extracted_data"]["contract_title"] == "Master Services Agreement"
    assert result["schema_name"] == "ContractExtraction"


@pytest.mark.asyncio
async def test_standalone_other_extraction_graph():
    """Other extraction graph executes with FakeLLMProvider."""
    fake_llm = FakeLLMProvider()
    graph = create_extraction_graph(llm_provider=fake_llm, db=None)

    initial_state = {
        "document_text": "General memo regarding company policies",
        "document_type": DocumentType.OTHER.value,
    }

    result = await graph.ainvoke(initial_state)
    assert result.get("error") is None
    assert result["extracted_data"]["title"] == "Company Announcement"
    assert result["schema_name"] == "OtherExtraction"


@pytest.mark.asyncio
async def test_standalone_extraction_graph_empty_text_error():
    """Extraction graph terminates with error if document text is empty."""
    fake_llm = FakeLLMProvider()
    graph = create_extraction_graph(llm_provider=fake_llm, db=None)

    initial_state = {
        "document_text": "",
        "document_type": DocumentType.INVOICE.value,
    }

    result = await graph.ainvoke(initial_state)
    assert result.get("error") is not None
    assert fake_llm.call_count == 0


@pytest.mark.asyncio
async def test_standalone_extraction_graph_missing_classification_error():
    """Extraction graph terminates with error if document_type is missing."""
    fake_llm = FakeLLMProvider()
    graph = create_extraction_graph(llm_provider=fake_llm, db=None)

    initial_state = {
        "document_text": "Some text",
        "document_type": "",
    }

    result = await graph.ainvoke(initial_state)
    assert result.get("error") is not None
    assert fake_llm.call_count == 0


# ---------------------------------------------------------------------------
# 3. API Integration Tests
# ---------------------------------------------------------------------------

async def _upload_ocr_classify_document(client: AsyncClient, filename: str = "invoice.pdf") -> str:
    """Helper to upload, OCR, and classify a document."""
    upload_resp = await client.post(
        "/api/v1/documents",
        files={"file": (filename, io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]

    ocr_resp = await client.post(f"/api/v1/documents/{doc_id}/ocr")
    assert ocr_resp.status_code == 200

    class_resp = await client.post(f"/api/v1/documents/{doc_id}/classify")
    assert class_resp.status_code == 200
    return doc_id


@pytest.mark.asyncio
async def test_extract_document_success(async_client: AsyncClient, fake_llm: FakeLLMProvider):
    """POST /documents/{id}/extract executes agent, transitions to EXTRACTED, returns data."""
    doc_id = await _upload_ocr_classify_document(async_client)

    response = await async_client.post(f"/api/v1/documents/{doc_id}/extract")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == doc_id
    assert data["document_type"] == DocumentType.INVOICE.value
    assert data["extraction_version"] == "1.0.0"
    assert data["status"] == DocumentStatus.EXTRACTED.value
    assert data["extracted_data"]["invoice_number"] == "INV-2026-001"
    assert data["extracted_data"]["total"] == 1650.0
    assert data["extracted_at"] is not None


@pytest.mark.asyncio
async def test_extract_document_persists_fields_and_history(async_client: AsyncClient):
    """Verify document GET reflects updated status and processing history."""
    doc_id = await _upload_ocr_classify_document(async_client)

    extract_resp = await async_client.post(f"/api/v1/documents/{doc_id}/extract")
    assert extract_resp.status_code == 200

    doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()

    assert doc_data["status"] == DocumentStatus.EXTRACTED.value

    # Verify history contains UPLOAD -> OCR -> CLASSIFICATION -> EXTRACTION
    history = doc_data["processing_history"]
    stages = [h["stage"] for h in history]
    assert ProcessingStage.UPLOAD.value in stages
    assert ProcessingStage.OCR.value in stages
    assert ProcessingStage.CLASSIFICATION.value in stages
    assert ProcessingStage.EXTRACTION.value in stages

    ext_hist = [h for h in history if h["stage"] == ProcessingStage.EXTRACTION.value][0]
    assert ext_hist["status"] == StageStatus.COMPLETED.value
    assert "Information extraction completed" in ext_hist["message"]
    assert ext_hist["completed_at"] is not None


@pytest.mark.asyncio
async def test_extract_document_before_ocr_returns_409(async_client: AsyncClient):
    """Attempting extraction on an un-OCR'd document returns 409 Conflict."""
    upload_resp = await async_client.post(
        "/api/v1/documents",
        files={"file": ("raw.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]

    response = await async_client.post(f"/api/v1/documents/{doc_id}/extract")
    assert response.status_code == 409
    assert "OCR must be completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_extract_document_before_classification_returns_409(async_client: AsyncClient):
    """Attempting extraction on an OCR'd but unclassified document returns 409 Conflict."""
    upload_resp = await async_client.post(
        "/api/v1/documents",
        files={"file": ("raw.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]

    ocr_resp = await async_client.post(f"/api/v1/documents/{doc_id}/ocr")
    assert ocr_resp.status_code == 200

    response = await async_client.post(f"/api/v1/documents/{doc_id}/extract")
    assert response.status_code == 409
    assert "classification must precede" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_extract_document_failure_flow(async_client: AsyncClient):
    """When LLM extraction fails, document status becomes FAILED and returns 422."""
    doc_id = await _upload_ocr_classify_document(async_client)

    failing_llm = FakeLLMProvider(should_fail=True)
    fastapi_app.dependency_overrides[get_llm_provider] = lambda: failing_llm

    try:
        response = await async_client.post(f"/api/v1/documents/{doc_id}/extract")
        assert response.status_code == 422
        assert "Simulated LLM generation error" in response.json()["detail"]

        # Check document status
        doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.status_code == 200
        doc_data = doc_resp.json()
        assert doc_data["status"] == DocumentStatus.FAILED.value
        assert "Simulated LLM generation error" in (doc_data["error_message"] or "")

        # Check history
        ext_hist = [h for h in doc_data["processing_history"] if h["stage"] == ProcessingStage.EXTRACTION.value][0]
        assert ext_hist["status"] == StageStatus.FAILED.value
        assert "Simulated LLM generation error" in (ext_hist["message"] or "")
    finally:
        fastapi_app.dependency_overrides.pop(get_llm_provider, None)


@pytest.mark.asyncio
async def test_extract_nonexistent_document_returns_404(async_client: AsyncClient):
    """POST /documents/{id}/extract for nonexistent document returns 404."""
    fake_id = str(uuid.uuid4())
    response = await async_client.post(f"/api/v1/documents/{fake_id}/extract")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_extraction_success(async_client: AsyncClient):
    """GET /documents/{id}/extraction returns extracted data after completion."""
    doc_id = await _upload_ocr_classify_document(async_client)
    await async_client.post(f"/api/v1/documents/{doc_id}/extract")

    response = await async_client.get(f"/api/v1/documents/{doc_id}/extraction")
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == doc_id
    assert data["document_type"] == DocumentType.INVOICE.value
    assert data["status"] == DocumentStatus.EXTRACTED.value
    assert data["extracted_data"]["invoice_number"] == "INV-2026-001"


@pytest.mark.asyncio
async def test_get_extraction_before_extract_returns_409(async_client: AsyncClient):
    """GET /documents/{id}/extraction returns 409 Conflict if not yet extracted."""
    doc_id = await _upload_ocr_classify_document(async_client)

    response = await async_client.get(f"/api/v1/documents/{doc_id}/extraction")
    assert response.status_code == 409
    assert "has not been extracted yet" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_extraction_nonexistent_document_returns_404(async_client: AsyncClient):
    """GET /documents/{id}/extraction for nonexistent document returns 404."""
    fake_id = str(uuid.uuid4())
    response = await async_client.get(f"/api/v1/documents/{fake_id}/extraction")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reextraction_flow(async_client: AsyncClient, fake_llm: FakeLLMProvider):
    """Running extraction a second time overwrites data and appends a new history record."""
    doc_id = await _upload_ocr_classify_document(async_client)

    # First extraction
    resp1 = await async_client.post(f"/api/v1/documents/{doc_id}/extract")
    assert resp1.status_code == 200
    assert resp1.json()["extracted_data"]["invoice_number"] == "INV-2026-001"

    # Modify mock return for second run
    fake_llm.extraction_override = InvoiceExtraction(
        invoice_number="INV-2026-REVISED-999",
        total=9999.0,
        currency="USD",
    )

    # Second extraction (re-extraction)
    resp2 = await async_client.post(f"/api/v1/documents/{doc_id}/extract")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["extracted_data"]["invoice_number"] == "INV-2026-REVISED-999"
    assert data2["extracted_data"]["total"] == 9999.0

    # Verify database document
    get_resp = await async_client.get(f"/api/v1/documents/{doc_id}/extraction")
    assert get_resp.status_code == 200
    assert get_resp.json()["extracted_data"]["invoice_number"] == "INV-2026-REVISED-999"

    # Verify history contains two EXTRACTION records
    doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
    history = doc_resp.json()["processing_history"]
    ext_records = [h for h in history if h["stage"] == ProcessingStage.EXTRACTION.value]
    assert len(ext_records) == 2
    assert ext_records[0]["status"] == StageStatus.COMPLETED.value
    assert ext_records[1]["status"] == StageStatus.COMPLETED.value
