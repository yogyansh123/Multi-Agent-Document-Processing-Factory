"""
workflows/__init__.py
=====================
Temporal workflow definitions for the Multi-Agent Document Processing Factory.
"""

from __future__ import annotations

from app.workflows.document_processing import DocumentProcessingWorkflow

__all__ = [
    "DocumentProcessingWorkflow",
]
