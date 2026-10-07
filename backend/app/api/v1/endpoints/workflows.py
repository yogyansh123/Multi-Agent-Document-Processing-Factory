"""
api/v1/endpoints/workflows.py
=============================
FastAPI endpoints for initiating and monitoring Temporal document processing workflows.

Routes:
    POST /documents/{document_id}/process  — Start end-to-end processing workflow (202 Accepted)
    GET  /documents/{document_id}/workflow — Query workflow status and execution stage
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import Cache, DbSession, Temporal
from app.core.enums import DocumentStatus
from app.core.logging import get_logger
from app.models.document import Document
from app.schemas.processing_status import ProcessingStatusResponse
from app.schemas.workflow import StartWorkflowResponse, WorkflowStatusResponse

logger = get_logger("app.api.workflows")

router = APIRouter()


@router.post(
    "/{document_id}/process",
    response_model=StartWorkflowResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start end-to-end document processing workflow",
    description=(
        "Initiates an asynchronous Temporal workflow orchestrating all pipeline activities: "
        "OCR → Classification → Extraction → Validation → Confidence Scoring. "
        "Returns immediately with workflow ID and run ID (202 Accepted)."
    ),
    responses={
        202: {"description": "Workflow initiated successfully."},
        404: {"description": "Document not found."},
        500: {"description": "Failed to dispatch workflow."},
    },
)
async def process_document(
    document_id: uuid.UUID,
    db: DbSession,
    temporal: Temporal,
    cache: Cache,
) -> StartWorkflowResponse:
    """Trigger the asynchronous Temporal processing workflow for a document."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found.",
        )

    workflow_id = temporal.get_workflow_id(str(document.id))
    if document.status in (
        DocumentStatus.APPROVED.value,
        DocumentStatus.REVIEW_REQUIRED.value,
        DocumentStatus.REJECTED.value,
    ):
        try:
            wf_info = await temporal.get_workflow_status(workflow_id)
            if wf_info.get("status") == "COMPLETED":
                return StartWorkflowResponse(
                    document_id=document.id,
                    workflow_id=workflow_id,
                    run_id=wf_info.get("run_id") or str(uuid.uuid4()),
                    status=document.status,
                    message="Document processing workflow has already completed.",
                )
        except Exception:
            pass

    document.status = DocumentStatus.PROCESSING.value
    await db.commit()
    await cache.delete_document_status(document_id)

    try:
        workflow_id, run_id = await temporal.start_document_processing_workflow(str(document.id))
        logger.info(
            "workflow.dispatched",
            document_id=str(document_id),
            workflow_id=workflow_id,
            run_id=run_id,
        )

        return StartWorkflowResponse(
            document_id=document.id,
            workflow_id=workflow_id,
            run_id=run_id,
            status=document.status,
            message="Document processing workflow initiated successfully.",
        )
    except Exception as exc:
        logger.error("workflow.dispatch_error", document_id=str(document_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate processing workflow: {exc}",
        ) from exc


@router.get(
    "/{document_id}/workflow",
    response_model=WorkflowStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get workflow execution status",
    description="Queries the current stage and state of the document's Temporal workflow execution.",
    responses={
        200: {"description": "Workflow status retrieved."},
        404: {"description": "Document not found."},
    },
)
async def get_workflow_status(
    document_id: uuid.UUID,
    db: DbSession,
    temporal: Temporal,
) -> WorkflowStatusResponse:
    """Query the status of an ongoing or completed processing workflow."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found.",
        )

    workflow_id = temporal.get_workflow_id(str(document.id))
    workflow_info = await temporal.get_workflow_status(workflow_id)

    return WorkflowStatusResponse(
        document_id=document.id,
        workflow_id=workflow_id,
        run_id=workflow_info.get("run_id"),
        workflow_status=workflow_info.get("status", "UNKNOWN"),
        current_stage=workflow_info.get("current_stage", "UNKNOWN"),
        document_status=document.status,
    )


@router.get(
    "/{document_id}/processing-status",
    response_model=ProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document processing status (Redis cache-first)",
    description=(
        "Returns the consolidated processing status of a document. "
        "Checks Redis cache first; falls back to PostgreSQL (durable source of truth) "
        "and active Temporal workflow queries on cache miss. Updates Redis on retrieval."
    ),
    responses={
        200: {"description": "Processing status retrieved successfully."},
        404: {"description": "Document not found."},
    },
)
async def get_processing_status(
    document_id: uuid.UUID,
    db: DbSession,
    temporal: Temporal,
    cache: Cache,
) -> ProcessingStatusResponse:
    """
    Retrieve document processing status with Redis cache-first strategy.
    """
    # 1. Check Redis cache first (accelerates terminal states)
    cached = await cache.get_document_status(document_id)
    if cached is not None:
        cached_status = cached.get("status", "")
        if cached_status in (
            DocumentStatus.APPROVED.value,
            DocumentStatus.REVIEW_REQUIRED.value,
            DocumentStatus.REJECTED.value,
            DocumentStatus.FAILED.value,
        ):
            logger.debug("processing_status.cache_hit", document_id=str(document_id))
            return ProcessingStatusResponse(**cached)

    # 2. Read PostgreSQL
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.processing_history),
            selectinload(Document.reviews),
        )
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found.",
        )

    # 3. Determine workflow ID and history milestones
    workflow_id = temporal.get_workflow_id(str(document.id))

    history = document.processing_history or []
    started_at = None
    completed_at = None
    failed_stage = None
    current_stage = None

    if history:
        sorted_history = sorted(
            history,
            key=lambda h: h.started_at if h.started_at else datetime.min.replace(tzinfo=timezone.utc),
        )
        started_at = sorted_history[0].started_at
        for h in sorted_history:
            if h.status == "FAILED":
                failed_stage = h.stage
            if h.status == "COMPLETED" and h.completed_at:
                completed_at = h.completed_at

    # Stage inference based on document lifecycle status
    if document.status in (DocumentStatus.APPROVED.value, DocumentStatus.REVIEW_REQUIRED.value):
        current_stage = "CONFIDENCE_SCORING"
    elif document.status == DocumentStatus.VALIDATED.value:
        current_stage = "VALIDATION"
    elif document.status == DocumentStatus.EXTRACTED.value:
        current_stage = "EXTRACTION"
    elif document.status == DocumentStatus.CLASSIFIED.value:
        current_stage = "CLASSIFICATION"
    elif document.status == DocumentStatus.OCR_COMPLETED.value:
        current_stage = "OCR"
    elif document.status == DocumentStatus.FAILED.value:
        current_stage = failed_stage or "FAILED"
    else:
        current_stage = "UPLOAD"

    # Review information and document attributes (extracted before any commit to prevent greenlet/lazy-load issues)
    latest_review = document.reviews[0] if (hasattr(document, "reviews") and document.reviews) else None
    review_id = str(latest_review.id) if latest_review else None
    review_status = latest_review.status if latest_review else None
    doc_id_str = str(document.id)
    doc_created_at = document.created_at
    doc_updated_at = document.updated_at
    doc_status = document.status
    doc_confidence = document.overall_confidence
    doc_recommendation = document.confidence_recommendation
    doc_error = document.error_message

    # 4. If active workflow exists and status is PROCESSING, query Temporal
    if doc_status == DocumentStatus.PROCESSING.value:
        try:
            wf_info = await temporal.get_workflow_status(workflow_id)
            wf_status = wf_info.get("status")
            t_stage = wf_info.get("current_stage")
            if wf_status == "FAILED":
                doc_status = DocumentStatus.FAILED.value
                doc_error = f"Workflow failed at stage {t_stage or 'UNKNOWN'}"
                failed_stage = t_stage or current_stage
                current_stage = "FAILED"
                document.status = doc_status
                document.error_message = doc_error
                await db.commit()
            elif wf_status == "COMPLETED":
                if doc_status == DocumentStatus.PROCESSING.value:
                    if doc_recommendation == "AUTO_APPROVE":
                        doc_status = DocumentStatus.APPROVED.value
                    elif doc_recommendation == "REVIEW_REQUIRED":
                        doc_status = DocumentStatus.REVIEW_REQUIRED.value
                    elif doc_confidence and doc_confidence >= settings.AUTO_APPROVAL_THRESHOLD:
                        doc_status = DocumentStatus.APPROVED.value
                    else:
                        doc_status = DocumentStatus.REVIEW_REQUIRED.value
                    document.status = doc_status
                    await db.commit()
                current_stage = "CONFIDENCE_SCORING"
            elif t_stage and t_stage not in ("UNKNOWN", "INITIALIZED"):
                current_stage = t_stage
            else:
                current_stage = "PROCESSING"
        except Exception:
            current_stage = "PROCESSING"

    # Assemble response payload
    status_dict = {
        "document_id": doc_id_str,
        "status": doc_status,
        "current_stage": current_stage,
        "workflow_id": workflow_id,
        "overall_confidence": doc_confidence,
        "confidence_recommendation": doc_recommendation,
        "started_at": started_at or doc_created_at,
        "updated_at": doc_updated_at,
        "completed_at": completed_at if doc_status in (
            DocumentStatus.APPROVED.value,
            DocumentStatus.REVIEW_REQUIRED.value,
            DocumentStatus.FAILED.value,
        ) else None,
        "failed_stage": failed_stage if doc_status == DocumentStatus.FAILED.value else None,
        "error_message": doc_error,
        "review_id": review_id,
        "review_status": review_status,
    }

    # 5. Update Redis cache: terminal states cached for default TTL; in-progress cached for 3s
    is_terminal = status_dict["status"] in (
        DocumentStatus.APPROVED.value,
        DocumentStatus.REVIEW_REQUIRED.value,
        DocumentStatus.REJECTED.value,
        DocumentStatus.FAILED.value,
    )
    ttl = None if is_terminal else 3
    await cache.set_document_status(document.id, status_dict, ttl_seconds=ttl)

    # 6. Return response
    return ProcessingStatusResponse(**status_dict)
