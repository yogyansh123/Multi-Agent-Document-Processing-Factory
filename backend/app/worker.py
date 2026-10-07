"""
worker.py
=========
Temporal Worker process for the Multi-Agent Document Processing Factory.

Registers DocumentProcessingWorkflow and the 5 pipeline activities:
- run_ocr_activity
- classify_document_activity
- extract_fields_activity
- validate_document_activity
- score_confidence_activity

Listens on settings.TEMPORAL_TASK_QUEUE.
"""

from __future__ import annotations

import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

from app.activities.document_activities import (
    classify_document_activity,
    extract_fields_activity,
    run_ocr_activity,
    score_confidence_activity,
    validate_document_activity,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.workflows.document_processing import DocumentProcessingWorkflow

logger = get_logger("app.worker")


async def run_worker() -> None:
    """Run the Temporal worker process."""
    host = f"{settings.TEMPORAL_HOST}:{settings.TEMPORAL_PORT}"
    logger.info(
        "worker.connecting",
        host=host,
        namespace=settings.TEMPORAL_NAMESPACE,
        queue=settings.TEMPORAL_TASK_QUEUE,
    )

    client = await Client.connect(host, namespace=settings.TEMPORAL_NAMESPACE)

    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[DocumentProcessingWorkflow],
        activities=[
            run_ocr_activity,
            classify_document_activity,
            extract_fields_activity,
            validate_document_activity,
            score_confidence_activity,
        ],
    )

    logger.info("worker.started", queue=settings.TEMPORAL_TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
