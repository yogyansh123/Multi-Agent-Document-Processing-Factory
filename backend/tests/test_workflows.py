"""
Tests for Temporal Workflow Orchestration: DocumentProcessingWorkflow.
"""

import uuid
import pytest
from temporalio import activity
from temporalio.worker import Worker
from temporalio.testing import WorkflowEnvironment

from app.activities.schemas import (
    DocumentActivityInput,
    DocumentActivityResult,
    DocumentWorkflowResult,
)
from app.workflows.document_processing import DocumentProcessingWorkflow


# Mock activities for workflow integration testing
@activity.defn(name="run_ocr_activity")
async def mock_run_ocr(input: DocumentActivityInput) -> DocumentActivityResult:
    return DocumentActivityResult(
        document_id=input.document_id,
        stage="OCR",
        status="COMPLETED",
        message="OCR complete",
        data={"page_count": 1},
    )


@activity.defn(name="classify_document_activity")
async def mock_classify(input: DocumentActivityInput) -> DocumentActivityResult:
    return DocumentActivityResult(
        document_id=input.document_id,
        stage="CLASSIFICATION",
        status="COMPLETED",
        message="Classified",
        data={"document_type": "INVOICE", "confidence": 0.95},
    )


@activity.defn(name="extract_fields_activity")
async def mock_extract(input: DocumentActivityInput) -> DocumentActivityResult:
    return DocumentActivityResult(
        document_id=input.document_id,
        stage="EXTRACTION",
        status="COMPLETED",
        message="Extracted",
        data={"document_type": "INVOICE"},
    )


@activity.defn(name="validate_document_activity")
async def mock_validate(input: DocumentActivityInput) -> DocumentActivityResult:
    return DocumentActivityResult(
        document_id=input.document_id,
        stage="VALIDATION",
        status="COMPLETED",
        message="Validated",
        data={"is_valid": True, "validation_score": 1.0},
    )


@activity.defn(name="score_confidence_activity")
async def mock_score_confidence(input: DocumentActivityInput) -> DocumentActivityResult:
    return DocumentActivityResult(
        document_id=input.document_id,
        stage="CONFIDENCE_SCORING",
        status="COMPLETED",
        message="Scored",
        data={
            "overall_confidence": 0.94,
            "recommendation": "APPROVED",
            "status": "APPROVED",
        },
    )


def test_workflow_initial_state():
    """Verify workflow instance initial state and query methods."""
    wf = DocumentProcessingWorkflow()
    assert wf.get_current_stage() == "INITIALIZED"
    assert wf.get_status() == "PROCESSING"
    assert wf.get_stages_completed() == []


@pytest.mark.asyncio
async def test_workflow_execution_in_temporal_environment():
    """
    Test running DocumentProcessingWorkflow inside Temporal WorkflowEnvironment.
    Verifies that all 5 activities are executed sequentially and the workflow returns
    a final DocumentWorkflowResult.
    """
    test_doc_id = str(uuid.uuid4())
    task_queue = "test-doc-processing-queue"

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[DocumentProcessingWorkflow],
            activities=[
                mock_run_ocr,
                mock_classify,
                mock_extract,
                mock_validate,
                mock_score_confidence,
            ],
        ):
            handle = await env.client.start_workflow(
                DocumentProcessingWorkflow.run,
                test_doc_id,
                id=f"wf-test-{test_doc_id}",
                task_queue=task_queue,
            )

            result: DocumentWorkflowResult = await handle.result()

            assert result.document_id == test_doc_id
            assert result.status == "APPROVED"
            assert result.document_type == "INVOICE"
            assert result.overall_confidence == 0.94
            assert result.recommendation == "APPROVED"
            assert result.stages_completed == [
                "OCR",
                "CLASSIFICATION",
                "EXTRACTION",
                "VALIDATION",
                "CONFIDENCE_SCORING",
            ]
