"""
agents/classification/nodes.py
==============================
LangGraph nodes for the Document Classification Agent workflow.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.classification.prompts import (
    CLASSIFICATION_SYSTEM_PROMPT,
    build_classification_user_prompt,
)
from app.agents.classification.schemas import DocumentClassification
from app.agents.classification.state import ClassificationState
from app.core.enums import DocumentStatus
from app.core.logging import get_logger
from app.models.document import Document
from app.services.llm.base import LLMProvider

logger = get_logger(__name__)


def create_load_document_text_node(db: AsyncSession | None = None):
    """
    Factory creating the load_document_text node.
    """

    async def load_document_text(state: ClassificationState) -> dict[str, str | None]:
        # Fast-path: text already supplied in state
        text = state.get("document_text")
        if text:
            return {"document_text": text}

        doc_id_str = state.get("document_id")
        if not doc_id_str:
            return {"error": "Missing document_id and document_text in state."}

        if db is None:
            return {"error": "No database session available to load document."}

        try:
            doc_id = uuid.UUID(doc_id_str)
        except ValueError:
            return {"error": f"Invalid document_id UUID: '{doc_id_str}'"}

        stmt = select(Document).where(Document.id == doc_id)
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()

        if document is None:
            return {"error": f"Document {doc_id} not found."}

        # Verify OCR has completed
        if document.status != DocumentStatus.OCR_COMPLETED.value:
            return {
                "error": (
                    f"Document {doc_id} has status '{document.status}'. "
                    "OCR must be completed before classification."
                )
            }

        if not document.ocr_text or not document.ocr_text.strip():
            return {"error": f"Document {doc_id} has no OCR text."}

        return {"document_text": document.ocr_text}

    return load_document_text


def create_classify_document_node(llm_provider: LLMProvider):
    """
    Factory creating the classify_document node.
    """

    async def classify_document(state: ClassificationState) -> dict[str, object]:
        if state.get("error"):
            return {}

        text = state.get("document_text") or ""
        user_prompt = build_classification_user_prompt(text)

        try:
            classification: DocumentClassification = await llm_provider.generate_structured(
                prompt=user_prompt,
                schema=DocumentClassification,
                system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
                temperature=0.0,
            )
            return {
                "document_type": classification.document_type.value,
                "confidence": classification.confidence,
                "reasoning": classification.reasoning,
                "signals": classification.signals,
            }
        except Exception as exc:
            logger.error(
                "classification.node.failed",
                error=str(exc),
                document_id=state.get("document_id"),
            )
            return {"error": f"LLM classification failed: {exc}"}

    return classify_document


def create_persist_classification_node(db: AsyncSession | None = None):
    """
    Factory creating the persist_classification node.
    """

    async def persist_classification(state: ClassificationState) -> dict[str, object]:
        if state.get("error") or db is None:
            return {}

        doc_id_str = state.get("document_id")
        if not doc_id_str:
            return {}

        try:
            doc_id = uuid.UUID(doc_id_str)
        except ValueError:
            return {"error": f"Invalid document_id UUID: '{doc_id_str}'"}

        stmt = select(Document).where(Document.id == doc_id)
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()

        if document is None:
            return {"error": f"Document {doc_id} not found during persistence."}

        now = datetime.now(timezone.utc)
        document.document_type = state.get("document_type")
        document.classification_confidence = state.get("confidence")
        document.classification_reasoning = state.get("reasoning")
        document.classification_signals = state.get("signals")
        document.classified_at = now
        document.status = DocumentStatus.CLASSIFIED.value

        await db.flush()
        return {}

    return persist_classification
