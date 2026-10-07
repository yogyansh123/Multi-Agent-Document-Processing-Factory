"""
workflows/document_processing.py
================================
Temporal workflow definition orchestrating the end-to-end document processing pipeline:
1. run_ocr_activity
2. classify_document_activity
3. extract_fields_activity
4. validate_document_activity
5. score_confidence_activity

Provides live queries for monitoring execution stage and status.
"""

from __future__ import annotations

from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.activities.document_activities import (
        classify_document_activity,
        extract_fields_activity,
        run_ocr_activity,
        score_confidence_activity,
        validate_document_activity,
    )
    from app.activities.schemas import (
        DocumentActivityInput,
        DocumentActivityResult,
        DocumentWorkflowResult,
    )


@workflow.defn
class DocumentProcessingWorkflow:
    """
    Durable, distributed orchestrator for document intelligence.

    Coordinates all processing activities sequentially with independent
    retry policies, timeouts, and observable stage queries.
    """

    def __init__(self) -> None:
        self._current_stage: str = "INITIALIZED"
        self._status: str = "PROCESSING"
        self._stages_completed: list[str] = []
        self._document_type: str | None = None
        self._overall_confidence: float | None = None
        self._recommendation: str | None = None

    @workflow.run
    async def run(self, document_id: str) -> DocumentWorkflowResult:
        """
        Execute the full document processing pipeline activities.
        """
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=2),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        activity_input = DocumentActivityInput(document_id=document_id)

        # 1. OCR Stage
        self._current_stage = "OCR"
        ocr_result: DocumentActivityResult = await workflow.execute_activity(
            run_ocr_activity,
            activity_input,
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=retry_policy,
        )
        self._stages_completed.append("OCR")

        # 2. Classification Stage
        self._current_stage = "CLASSIFICATION"
        classify_result: DocumentActivityResult = await workflow.execute_activity(
            classify_document_activity,
            activity_input,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy,
        )
        self._stages_completed.append("CLASSIFICATION")
        self._document_type = classify_result.data.get("document_type")

        # 3. Extraction Stage
        self._current_stage = "EXTRACTION"
        extract_result: DocumentActivityResult = await workflow.execute_activity(
            extract_fields_activity,
            activity_input,
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=retry_policy,
        )
        self._stages_completed.append("EXTRACTION")

        # 4. Validation Stage
        self._current_stage = "VALIDATION"
        validate_result: DocumentActivityResult = await workflow.execute_activity(
            validate_document_activity,
            activity_input,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy,
        )
        self._stages_completed.append("VALIDATION")

        # 5. Confidence Scoring Stage
        self._current_stage = "CONFIDENCE_SCORING"
        confidence_result: DocumentActivityResult = await workflow.execute_activity(
            score_confidence_activity,
            activity_input,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )
        self._stages_completed.append("CONFIDENCE_SCORING")
        self._overall_confidence = confidence_result.data.get("overall_confidence")
        self._recommendation = confidence_result.data.get("recommendation")
        self._status = confidence_result.data.get("status", "APPROVED")
        self._current_stage = "COMPLETED"

        return DocumentWorkflowResult(
            document_id=document_id,
            status=self._status,
            document_type=self._document_type,
            overall_confidence=self._overall_confidence,
            recommendation=self._recommendation,
            stages_completed=self._stages_completed,
        )

    @workflow.query
    def get_current_stage(self) -> str:
        """Query currently active or last completed stage."""
        return self._current_stage

    @workflow.query
    def get_status(self) -> str:
        """Query overall workflow status."""
        return self._status

    @workflow.query
    def get_stages_completed(self) -> list[str]:
        """Query list of completed stages."""
        return self._stages_completed
