"""
tests/test_validation.py
========================
Tests for Step 6: Validation Agent (Deterministic Rules + LLM Semantic Validation).

Deterministic, zero-external-API tests using FakeLLMProvider and in-memory SQLite.
"""

from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.validation.graph import create_validation_graph
from app.agents.validation.rules import validate_deterministic
from app.agents.validation.schemas import (
    SemanticValidationIssue,
    SemanticValidationResult,
    ValidationIssue,
    ValidationResult,
)
from app.core.enums import DocumentStatus, DocumentType, ProcessingStage, ValidationSeverity
from app.models.document import Document
from app.models.processing_history import ProcessingHistory
from tests.conftest import FakeLLMProvider


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------


def test_validation_issue_schema():
    issue = ValidationIssue(
        code="ARITHMETIC_MISMATCH",
        field="line_items[0].total_amount",
        message="Item total does not match quantity * price",
        severity=ValidationSeverity.ERROR,
        actual_value=120.0,
        expected_value=100.0,
    )
    assert issue.code == "ARITHMETIC_MISMATCH"
    assert issue.severity == ValidationSeverity.ERROR
    assert issue.actual_value == 120.0


def test_validation_result_schema():
    res = ValidationResult(
        is_valid=True,
        issues=[],
        rules_checked=["INV_REQUIRED_FIELDS", "INV_LINE_ITEM_ARITHMETIC"],
        validation_score=1.0,
    )
    assert res.is_valid is True
    assert res.validation_score == 1.0
    assert len(res.rules_checked) == 2


# ---------------------------------------------------------------------------
# Deterministic Rules: Invoice
# ---------------------------------------------------------------------------


def test_invoice_deterministic_valid():
    data = {
        "invoice_number": "INV-001",
        "vendor": {"name": "Acme Inc"},
        "subtotal": 100.0,
        "tax_amount": 10.0,
        "discount": 0.0,
        "total_amount": 110.0,
        "invoice_date": "2026-01-01",
        "due_date": "2026-01-31",
        "currency": "USD",
        "line_items": [
            {"description": "Item 1", "quantity": 2, "unit_price": 50.0, "total_amount": 100.0}
        ],
    }
    issues, rules = validate_deterministic("INVOICE", data)
    assert len(issues) == 0
    assert "INV_REQUIRED_FIELDS" in rules
    assert "INV_LINE_ITEM_ARITHMETIC" in rules
    assert "INV_SUBTOTAL_ARITHMETIC" in rules
    assert "INV_TOTAL_ARITHMETIC" in rules


def test_invoice_deterministic_missing_required_fields():
    data = {"subtotal": 100.0}
    issues, _ = validate_deterministic("INVOICE", data)
    codes = [i.code for i in issues]
    assert "MISSING_INVOICE_NUMBER" in codes
    assert "MISSING_VENDOR" in codes
    assert "MISSING_TOTAL_AMOUNT" in codes


def test_invoice_deterministic_arithmetic_mismatches():
    data = {
        "invoice_number": "INV-002",
        "vendor": {"name": "Acme Inc"},
        "subtotal": 100.0,
        "tax_amount": 5.0,
        "total_amount": 150.0,  # 100 + 5 != 150
        "line_items": [
            {"description": "Item 1", "quantity": 2, "unit_price": 40.0, "total_amount": 100.0}  # 2 * 40 != 100
        ],
    }
    issues, _ = validate_deterministic("INVOICE", data)
    codes = [i.code for i in issues]
    assert "LINE_ITEM_ARITHMETIC_MISMATCH" in codes
    assert "TOTAL_ARITHMETIC_MISMATCH" in codes


def test_invoice_deterministic_invalid_date_order():
    data = {
        "invoice_number": "INV-003",
        "vendor": {"name": "Acme Inc"},
        "total_amount": 50.0,
        "invoice_date": "2026-02-15",
        "due_date": "2026-02-01",  # Due date before invoice date
    }
    issues, _ = validate_deterministic("INVOICE", data)
    codes = [i.code for i in issues]
    assert "DATE_ORDER_INVALID" in codes
    assert any(i.severity == ValidationSeverity.ERROR for i in issues if i.code == "DATE_ORDER_INVALID")


def test_invoice_deterministic_negative_amounts():
    data = {
        "invoice_number": "INV-004",
        "vendor": {"name": "Acme Inc"},
        "total_amount": -50.0,
    }
    issues, _ = validate_deterministic("INVOICE", data)
    codes = [i.code for i in issues]
    assert "NEGATIVE_VALUE" in codes


# ---------------------------------------------------------------------------
# Deterministic Rules: Receipt, Purchase Order, Contract, Other
# ---------------------------------------------------------------------------


def test_receipt_deterministic_rules():
    # Missing merchant & total
    issues, _ = validate_deterministic("RECEIPT", {})
    codes = [i.code for i in issues]
    assert "MISSING_MERCHANT" in codes
    assert "MISSING_TOTAL_AMOUNT" in codes

    # Valid receipt
    valid_receipt = {
        "merchant": "Supermarket",
        "total_amount": 25.0,
        "subtotal": 25.0,
        "items": [{"description": "Milk", "quantity": 1, "unit_price": 25.0, "amount": 25.0}],
    }
    issues2, _ = validate_deterministic("RECEIPT", valid_receipt)
    assert len(issues2) == 0


def test_purchase_order_deterministic_rules():
    po_data = {
        "po_number": "PO-100",
        "buyer": {"name": "Buyer Corp"},
        "supplier": {"name": "Seller LLC"},
        "subtotal": 500.0,
        "total_amount": 500.0,
        "po_date": "2026-01-20",
        "delivery_date": "2026-01-10",  # earlier than po_date
    }
    issues, _ = validate_deterministic("PURCHASE_ORDER", po_data)
    codes = [i.code for i in issues]
    assert "DATE_ORDER_INVALID" in codes


def test_contract_deterministic_rules():
    # 0 parties -> ERROR, expiration < effective -> ERROR
    contract_data = {
        "contract_title": "NDA",
        "parties": [],
        "effective_date": "2026-05-01",
        "expiration_date": "2026-01-01",
    }
    issues, _ = validate_deterministic("CONTRACT", contract_data)
    codes = [i.code for i in issues]
    assert "MISSING_CONTRACT_PARTIES" in codes
    assert "DATE_ORDER_INVALID" in codes


def test_other_deterministic_rules():
    other_data = {
        "title": "Meeting Notes",
        "key_values": [{"key": "", "value": "val1"}],
    }
    issues, _ = validate_deterministic("OTHER", other_data)
    codes = [i.code for i in issues]
    assert "EMPTY_KEY_NAME" in codes


# ---------------------------------------------------------------------------
# Standalone LangGraph Validation Graph Execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_standalone_validation_graph_valid():
    graph = create_validation_graph(llm_provider=None, db=None)
    state = {
        "document_id": str(uuid.uuid4()),
        "document_text": "Sample text",
        "document_type": "INVOICE",
        "extracted_data": {
            "invoice_number": "INV-777",
            "vendor": {"name": "Corp"},
            "total_amount": 100.0,
            "subtotal": 100.0,
        },
    }
    result = await graph.ainvoke(state)
    assert result.get("error") is None
    assert result["is_valid"] is True
    assert result["validation_score"] == 1.0
    assert result["validation_result"]["is_valid"] is True


@pytest.mark.asyncio
async def test_standalone_validation_graph_with_semantic_llm():
    fake_llm = FakeLLMProvider()
    graph = create_validation_graph(llm_provider=fake_llm, db=None)
    state = {
        "document_id": str(uuid.uuid4()),
        "document_text": "Sample text",
        "document_type": "INVOICE",
        "extracted_data": {
            "invoice_number": "INV-888",
            "vendor": {"name": "Vendor A"},
            "total_amount": 200.0,
            "subtotal": 200.0,
        },
    }
    result = await graph.ainvoke(state)
    assert result.get("error") is None
    assert result["is_valid"] is True
    assert "SEMANTIC_COHERENCE_CHECK" in result["rules_checked"]
    assert fake_llm.call_count == 1


@pytest.mark.asyncio
async def test_standalone_validation_graph_detects_errors():
    graph = create_validation_graph(llm_provider=None, db=None)
    state = {
        "document_id": str(uuid.uuid4()),
        "document_text": "Sample text",
        "document_type": "INVOICE",
        "extracted_data": {
            # Missing invoice_number and total_amount
            "subtotal": 100.0,
        },
    }
    result = await graph.ainvoke(state)
    assert result["is_valid"] is False
    assert result["validation_score"] < 1.0


# ---------------------------------------------------------------------------
# API Endpoint Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_document_success(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="valid_invoice.pdf",
        stored_filename="valid_invoice.pdf",
        file_path="storage/valid_invoice.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.EXTRACTED.value,
        ocr_text="Invoice #INV-2026-001\nTotal: $100.00",
        document_type=DocumentType.INVOICE.value,
        extracted_data={
            "invoice_number": "INV-2026-001",
            "vendor": {"name": "Acme Corp"},
            "total_amount": 100.0,
            "subtotal": 100.0,
        },
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    response = await async_client.post(f"/api/v1/documents/{doc.id}/validate")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == str(doc.id)
    assert data["document_type"] == "INVOICE"
    assert data["is_valid"] is True
    assert data["validation_score"] == 1.0
    assert data["status"] == DocumentStatus.VALIDATED.value


@pytest.mark.asyncio
async def test_validate_document_before_ocr_returns_409(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="no_ocr.pdf",
        stored_filename="no_ocr.pdf",
        file_path="storage/no_ocr.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.UPLOADED.value,
    )
    db_session.add(doc)
    await db_session.commit()

    response = await async_client.post(f"/api/v1/documents/{doc.id}/validate")
    assert response.status_code == 409
    assert "OCR has not completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validate_document_before_classification_returns_409(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="no_class.pdf",
        stored_filename="no_class.pdf",
        file_path="storage/no_class.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.OCR_COMPLETED.value,
        ocr_text="Some text",
        document_type=None,
    )
    db_session.add(doc)
    await db_session.commit()

    response = await async_client.post(f"/api/v1/documents/{doc.id}/validate")
    assert response.status_code == 409
    assert "document has not been classified" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validate_document_before_extraction_returns_409(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="no_extract.pdf",
        stored_filename="no_extract.pdf",
        file_path="storage/no_extract.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.CLASSIFIED.value,
        ocr_text="Some text",
        document_type="INVOICE",
        extracted_data=None,
    )
    db_session.add(doc)
    await db_session.commit()

    response = await async_client.post(f"/api/v1/documents/{doc.id}/validate")
    assert response.status_code == 409
    assert "information extraction has not completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validate_nonexistent_document_returns_404(
    async_client: AsyncClient,
):
    random_id = uuid.uuid4()
    response = await async_client.post(f"/api/v1/documents/{random_id}/validate")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_validation_success(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="doc.pdf",
        stored_filename="doc.pdf",
        file_path="storage/doc.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.VALIDATED.value,
        document_type="INVOICE",
        validation_result={"is_valid": True, "issues": [], "rules_checked": ["R1"]},
        validation_score=1.0,
    )
    db_session.add(doc)
    await db_session.commit()

    response = await async_client.get(f"/api/v1/documents/{doc.id}/validation")
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["validation_score"] == 1.0


@pytest.mark.asyncio
async def test_get_validation_before_validate_returns_409(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    doc = Document(
        original_filename="doc.pdf",
        stored_filename="doc.pdf",
        file_path="storage/doc.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.EXTRACTED.value,
        document_type="INVOICE",
        validation_result=None,
    )
    db_session.add(doc)
    await db_session.commit()

    response = await async_client.get(f"/api/v1/documents/{doc.id}/validation")
    assert response.status_code == 409
