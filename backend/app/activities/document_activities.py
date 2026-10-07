"""
activities/document_activities.py
=================================
Temporal activity definitions for the document processing pipeline stages:
1. run_ocr_activity
2. classify_document_activity
3. extract_fields_activity
4. validate_document_activity
5. score_confidence_activity

Each activity is idempotent, manages its database session, and delegates
to the existing domain services.
"""

from __future__ import annotations

import uuid
from temporalio import activity

from app.activities.schemas import DocumentActivityInput, DocumentActivityResult
from app.core.enums import ProcessingStage, StageStatus
from app.core.logging import get_logger
from app.db.session import get_session_maker
from app.services.classification_service import ClassificationService
from app.services.confidence_service import ConfidenceService
from app.services.extraction_service import ExtractionService
from app.services.llm.factory import get_llm_provider
from app.services.ocr.factory import get_ocr_provider
from app.services.ocr_service import OcrService
from app.services.storage.factory import get_storage_provider
from app.services.validation_service import ValidationService

logger = get_logger("app.activities.document")

_custom_providers: dict[str, object] = {}


def set_activity_providers(
    storage=None,
    ocr=None,
    llm=None,
) -> None:
    """Set custom providers for test execution."""
    if storage is not None:
        _custom_providers["storage"] = storage
    if ocr is not None:
        _custom_providers["ocr"] = ocr
    if llm is not None:
        _custom_providers["llm"] = llm


@activity.defn
async def run_ocr_activity(input: DocumentActivityInput) -> DocumentActivityResult:
    """
    Temporal activity: executes OCR extraction on an uploaded document.
    """
    logger.info("activity.run_ocr.started", document_id=input.document_id)
    doc_uuid = uuid.UUID(input.document_id)
    session_maker = get_session_maker()

    async with session_maker() as session:
        storage = _custom_providers.get("storage") or get_storage_provider()
        ocr = _custom_providers.get("ocr") or get_ocr_provider()
        service = OcrService(db=session, storage=storage, ocr=ocr)
        doc = await service.run_ocr(doc_uuid)
        await session.commit()

        logger.info("activity.run_ocr.completed", document_id=input.document_id)
        return DocumentActivityResult(
            document_id=str(doc.id),
            stage=ProcessingStage.OCR.value,
            status=StageStatus.COMPLETED.value,
            message="OCR completed successfully",
            data={
                "ocr_provider": doc.ocr_provider,
                "page_count": doc.ocr_page_count or 1,
            },
        )


@activity.defn
async def classify_document_activity(input: DocumentActivityInput) -> DocumentActivityResult:
    """
    Temporal activity: executes document classification using LangGraph Classification Agent.
    """
    logger.info("activity.classify.started", document_id=input.document_id)
    doc_uuid = uuid.UUID(input.document_id)
    session_maker = get_session_maker()

    async with session_maker() as session:
        llm = _custom_providers.get("llm") or get_llm_provider()
        service = ClassificationService(db=session, llm=llm)
        resp = await service.classify_document(doc_uuid)
        await session.commit()

        logger.info(
            "activity.classify.completed",
            document_id=input.document_id,
            document_type=resp.document_type,
            confidence=resp.classification_confidence,
        )
        return DocumentActivityResult(
            document_id=str(resp.id),
            stage=ProcessingStage.CLASSIFICATION.value,
            status=StageStatus.COMPLETED.value,
            message=f"Classified as {resp.document_type}",
            data={
                "document_type": resp.document_type,
                "confidence": resp.classification_confidence,
            },
        )


@activity.defn
async def extract_fields_activity(input: DocumentActivityInput) -> DocumentActivityResult:
    """
    Temporal activity: executes structured field extraction using LangGraph Extraction Agent.
    """
    logger.info("activity.extract.started", document_id=input.document_id)
    doc_uuid = uuid.UUID(input.document_id)
    session_maker = get_session_maker()

    async with session_maker() as session:
        llm = _custom_providers.get("llm") or get_llm_provider()
        service = ExtractionService(db=session, llm=llm)
        doc = await service.extract_document(doc_uuid)
        await session.commit()

        logger.info(
            "activity.extract.completed",
            document_id=input.document_id,
            document_type=doc.document_type,
        )
        return DocumentActivityResult(
            document_id=str(doc.id),
            stage=ProcessingStage.EXTRACTION.value,
            status=StageStatus.COMPLETED.value,
            message="Structured field extraction completed",
            data={
                "document_type": doc.document_type,
                "extraction_version": doc.extraction_version,
            },
        )


@activity.defn
async def validate_document_activity(input: DocumentActivityInput) -> DocumentActivityResult:
    """
    Temporal activity: executes deterministic rules & LLM semantic validation.
    """
    logger.info("activity.validate.started", document_id=input.document_id)
    doc_uuid = uuid.UUID(input.document_id)
    session_maker = get_session_maker()

    async with session_maker() as session:
        llm = _custom_providers.get("llm") or get_llm_provider()
        service = ValidationService(db=session, llm_provider=llm)
        resp = await service.validate_document(doc_uuid)
        await session.commit()

        logger.info(
            "activity.validate.completed",
            document_id=input.document_id,
            is_valid=resp.is_valid,
            validation_score=resp.validation_score,
        )
        return DocumentActivityResult(
            document_id=str(resp.document_id),
            stage=ProcessingStage.VALIDATION.value,
            status=StageStatus.COMPLETED.value,
            message=f"Validation completed (score: {resp.validation_score})",
            data={
                "is_valid": resp.is_valid,
                "validation_score": resp.validation_score,
                "issues_count": len(resp.issues),
            },
        )


@activity.defn
async def score_confidence_activity(input: DocumentActivityInput) -> DocumentActivityResult:
    """
    Temporal activity: calculates multi-factor confidence and routes to APPROVED or REVIEW_REQUIRED.
    """
    logger.info("activity.confidence.started", document_id=input.document_id)
    doc_uuid = uuid.UUID(input.document_id)
    session_maker = get_session_maker()

    async with session_maker() as session:
        service = ConfidenceService(db=session)
        resp = await service.calculate_confidence(doc_uuid)
        await session.commit()

        logger.info(
            "activity.confidence.completed",
            document_id=input.document_id,
            overall_confidence=resp.overall_confidence,
            recommendation=resp.recommendation,
            status=resp.status,
        )
        try:
            from app.services.cache import get_redis_service
            redis_svc = await get_redis_service()
            await redis_svc.delete_document_status(resp.document_id)
        except Exception:
            pass
        return DocumentActivityResult(
            document_id=str(resp.document_id),
            stage=ProcessingStage.CONFIDENCE_SCORING.value,
            status=StageStatus.COMPLETED.value,
            message=f"Decision: {resp.recommendation} (Status: {resp.status})",
            data={
                "overall_confidence": resp.overall_confidence,
                "recommendation": resp.recommendation,
                "status": resp.status,
            },
        )
