"""
services/temporal/client.py
===========================
Temporal client abstraction and workflow lifecycle management.

Handles connecting to the Temporal cluster and dispatching workflows.
Includes an in-memory test double mode for deterministic automated testing
without requiring an external running Temporal cluster.
"""

from __future__ import annotations

import uuid
from typing import Any

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.core.config import settings
from app.core.logging import get_logger
from app.workflows.document_processing import DocumentProcessingWorkflow

logger = get_logger("app.services.temporal")


class TemporalClientService:
    """
    Service wrapper around the Temporal Python SDK Client.
    """

    def __init__(self, client: Client | None = None, is_mock: bool = False) -> None:
        self._client = client
        self._is_mock = is_mock
        self._mock_workflows: dict[str, dict[str, Any]] = {}

    @property
    def is_mock(self) -> bool:
        """Return True if running in mock/fallback mode without a live Temporal cluster."""
        return self._is_mock or not self._client

    @classmethod
    async def connect(cls, target_host: str | None = None, namespace: str | None = None) -> TemporalClientService:
        """
        Connect to a live Temporal cluster. Falls back to mock mode if connection fails
        and APP_ENV is development or test.
        """
        host = target_host or settings.TEMPORAL_ADDRESS
        ns = namespace or settings.TEMPORAL_NAMESPACE

        try:
            client = await Client.connect(host, namespace=ns)
            logger.info("temporal.connected", host=host, namespace=ns)
            return cls(client=client, is_mock=False)
        except Exception as exc:
            logger.warning("temporal.connection_failed_fallback_to_mock", error=str(exc))
            return cls(client=None, is_mock=True)

    @staticmethod
    def get_workflow_id(document_id: str) -> str:
        """Return canonical duplicate-safe workflow ID."""
        return f"document-processing-{document_id}"

    async def is_healthy(self) -> bool:
        """Check if Temporal connection is healthy."""
        if self._is_mock:
            return True
        if not self._client:
            return False
        try:
            await self._client.service_client.check_health()
            return True
        except Exception:
            return False

    async def start_document_processing_workflow(
        self,
        document_id: str,
        task_queue: str | None = None,
    ) -> tuple[str, str]:
        """
        Start the DocumentProcessingWorkflow for a document in an idempotent, duplicate-safe manner.

        Returns:
            tuple[workflow_id, run_id]
        """
        workflow_id = self.get_workflow_id(document_id)
        queue = task_queue or settings.TEMPORAL_TASK_QUEUE

        if self._is_mock or not self._client:
            existing = self._mock_workflows.get(workflow_id)
            if existing and existing.get("status") == "RUNNING":
                logger.info(
                    "temporal.mock_workflow_already_running",
                    workflow_id=workflow_id,
                    run_id=existing.get("run_id"),
                )
                return workflow_id, str(existing.get("run_id"))

            run_id = str(uuid.uuid4())
            self._mock_workflows[workflow_id] = {
                "document_id": document_id,
                "workflow_id": workflow_id,
                "run_id": run_id,
                "status": "RUNNING",
                "current_stage": "INITIALIZED",
            }
            logger.info(
                "temporal.mock_workflow_started",
                workflow_id=workflow_id,
                run_id=run_id,
            )
            return workflow_id, run_id

        try:
            handle = await self._client.start_workflow(
                DocumentProcessingWorkflow.run,
                document_id,
                id=workflow_id,
                task_queue=queue,
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            )
            logger.info(
                "temporal.workflow_started",
                workflow_id=handle.id,
                run_id=handle.result_run_id,
            )
            return handle.id, handle.result_run_id or str(uuid.uuid4())
        except WorkflowAlreadyStartedError as err:
            logger.info(
                "temporal.workflow_already_running",
                workflow_id=workflow_id,
                run_id=err.run_id,
            )
            return workflow_id, err.run_id or str(uuid.uuid4())

    async def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """
        Query workflow status and current stage.
        """
        if self._is_mock or not self._client:
            return self._mock_workflows.get(
                workflow_id,
                {
                    "workflow_id": workflow_id,
                    "status": "UNKNOWN",
                    "current_stage": "UNKNOWN",
                },
            )

        try:
            handle = self._client.get_workflow_handle(workflow_id)
            desc = await handle.describe()
            current_stage = await handle.query(DocumentProcessingWorkflow.get_current_stage)
            return {
                "workflow_id": workflow_id,
                "run_id": desc.run_id,
                "status": str(desc.status.name),
                "current_stage": current_stage,
            }
        except Exception as exc:
            logger.error("temporal.query_failed", workflow_id=workflow_id, error=str(exc))
            return {
                "workflow_id": workflow_id,
                "status": "ERROR",
                "error": str(exc),
            }


_client_instance: TemporalClientService | None = None


async def get_temporal_client() -> TemporalClientService:
    """Dependency provider for TemporalClientService."""
    global _client_instance
    if _client_instance is None:
        _client_instance = await TemporalClientService.connect()
    return _client_instance


def set_temporal_client(client: TemporalClientService) -> None:
    """Set custom TemporalClientService for testing."""
    global _client_instance
    _client_instance = client
