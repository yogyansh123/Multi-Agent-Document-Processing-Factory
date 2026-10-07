"""
tests/test_activities.py
========================
Unit tests for Temporal document processing activities.

Verifies each activity executes against the database and returns structured results.
"""

from __future__ import annotations

import io
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.document_activities import (
    classify_document_activity,
    extract_fields_activity,
    run_ocr_activity,
    score_confidence_activity,
    set_activity_providers,
    validate_document_activity,
)
from app.activities.schemas import DocumentActivityInput
from app.core.enums import DocumentStatus
from app.models.document import Document
from app.services.storage.local import LocalStorageProvider
from tests.conftest import MockOCRProvider, FakeLLMProvider


@pytest.mark.asyncio
async def test_document_activities_sequential_execution(
    db_session: AsyncSession,
    tmp_storage_dir: str,
):
    """
    Test all 5 activities executing sequentially on a document.
    """
    storage_provider = LocalStorageProvider(storage_root=tmp_storage_dir)
    mock_ocr = MockOCRProvider()
    fake_llm = FakeLLMProvider()
    set_activity_providers(storage=storage_provider, ocr=mock_ocr, llm=fake_llm)

    # Save a physical file so OCR activity finds it
    stored_file = await storage_provider.save(
        b"%PDF-1.4 sample content",
        "invoice_act.pdf",
        "application/pdf",
    )

    # Create uploaded document
    doc = Document(
        original_filename="invoice_act.pdf",
        stored_filename=stored_file.stored_filename,
        file_path=stored_file.file_path,
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1024,
        status=DocumentStatus.UPLOADED.value,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    act_input = DocumentActivityInput(document_id=str(doc.id))

    # 1. OCR Activity
    ocr_result = await run_ocr_activity(act_input)
    assert ocr_result.status == "COMPLETED"
    assert ocr_result.stage == "OCR"

    # 2. Classify Activity
    class_result = await classify_document_activity(act_input)
    assert class_result.status == "COMPLETED"
    assert class_result.stage == "CLASSIFICATION"
    assert class_result.data.get("document_type") is not None

    # 3. Extract Activity
    extract_result = await extract_fields_activity(act_input)
    assert extract_result.status == "COMPLETED"
    assert extract_result.stage == "EXTRACTION"

    # 4. Validate Activity
    val_result = await validate_document_activity(act_input)
    assert val_result.status == "COMPLETED"
    assert val_result.stage == "VALIDATION"
    assert "validation_score" in val_result.data

    # 5. Confidence Activity
    conf_result = await score_confidence_activity(act_input)
    assert conf_result.status == "COMPLETED"
    assert conf_result.stage == "CONFIDENCE_SCORING"
    assert conf_result.data.get("recommendation") in ("AUTO_APPROVE", "REVIEW_REQUIRED")
