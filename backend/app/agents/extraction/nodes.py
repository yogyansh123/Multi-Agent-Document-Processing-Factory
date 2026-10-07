"""
agents/extraction/nodes.py
==========================
LangGraph nodes for the Information Extraction Agent workflow.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.extraction.prompts import (
    EXTRACTION_PROMPT_VERSION,
    build_extraction_user_prompt,
    get_extraction_prompt,
)
from app.agents.extraction.schemas import get_extraction_schema
from app.agents.extraction.state import ExtractionState
from app.core.enums import DocumentStatus
from app.core.logging import get_logger
from app.models.document import Document
from app.services.llm.base import LLMProvider

logger = get_logger(__name__)


def create_load_document_node(db: AsyncSession | None = None):
    """
    Factory creating the load_document node.
    Loads OCR text and validates OCR completion.
    """

    async def load_document(state: ExtractionState) -> dict[str, object]:
        if state.get("document_text"):
            return {}

        doc_id_str = state.get("document_id")
        if not doc_id_str:
            return {"error": "Missing document_id and document_text in extraction state."}

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

        if not document.ocr_text or not document.ocr_text.strip():
            return {
                "error": (
                    f"Document {doc_id} has not completed OCR or contains no text "
                    f"(status: '{document.status}')."
                )
            }

        return {
            "document_text": document.ocr_text,
            "document_type": state.get("document_type") or document.document_type,
        }

    return load_document


def create_load_classification_node(db: AsyncSession | None = None):
    """
    Factory creating the load_classification node.
    Verifies that the document has a classified document_type.
    """

    async def load_classification(state: ExtractionState) -> dict[str, object]:
        if state.get("error"):
            return {}

        doc_type = state.get("document_type")
        if doc_type:
            return {}

        doc_id_str = state.get("document_id")
        if not doc_id_str or db is None:
            return {"error": "Document type is missing and cannot be loaded."}

        try:
            doc_id = uuid.UUID(doc_id_str)
        except ValueError:
            return {"error": f"Invalid document_id UUID: '{doc_id_str}'"}

        stmt = select(Document).where(Document.id == doc_id)
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()

        if document is None:
            return {"error": f"Document {doc_id} not found."}

        if not document.document_type:
            return {
                "error": (
                    f"Document {doc_id} has not been classified yet "
                    f"(status: '{document.status}'). Classification must precede extraction."
                )
            }

        return {"document_type": document.document_type}

    return load_classification


def create_select_schema_node():
    """
    Selects the Pydantic schema and version based on document_type.
    """

    async def select_schema(state: ExtractionState) -> dict[str, object]:
        if state.get("error"):
            return {}

        doc_type = state.get("document_type") or "OTHER"
        schema_cls = get_extraction_schema(doc_type)

        return {
            "schema_name": schema_cls.__name__,
            "extraction_version": EXTRACTION_PROMPT_VERSION,
        }

    return select_schema


def create_extract_information_node(llm_provider: LLMProvider):
    """
    Factory creating the extract_information node.
    Invokes LLM with the type-specific structured schema.
    """

    async def extract_information(state: ExtractionState) -> dict[str, object]:
        if state.get("error"):
            return {}

        doc_type = state.get("document_type") or "OTHER"
        text = state.get("document_text") or ""
        schema_cls = get_extraction_schema(doc_type)
        system_prompt = get_extraction_prompt(doc_type)
        user_prompt = build_extraction_user_prompt(text, doc_type)

        try:
            logger.info(
                "extraction.node.invoking_llm",
                document_type=doc_type,
                schema=schema_cls.__name__,
            )
            extracted_obj = await llm_provider.generate_structured(
                prompt=user_prompt,
                schema=schema_cls,
                system_prompt=system_prompt,
                temperature=0.0,
            )
            # Serialize model to dictionary
            return {"extracted_data": extracted_obj.model_dump()}
        except Exception as exc:
            logger.error(
                "extraction.node.failed",
                document_id=state.get("document_id"),
                error=str(exc),
            )
            return {"error": f"LLM information extraction failed: {exc}"}

    return extract_information


def create_persist_extraction_node(db: AsyncSession | None = None):
    """
    Factory creating the persist_extraction node.
    Saves extracted data into the Document database record.
    """

    async def persist_extraction(state: ExtractionState) -> dict[str, object]:
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
        document.extracted_data = state.get("extracted_data")
        document.extraction_version = state.get("extraction_version") or EXTRACTION_PROMPT_VERSION
        document.extracted_at = now
        document.status = DocumentStatus.EXTRACTED.value

        await db.flush()
        return {}

    return persist_extraction
