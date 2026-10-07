"""
agents/__init__.py
==================
LangGraph-based AI agents for document processing.

Each sub-package contains an independently testable agent:

- classification/  — Determines document type (Invoice, Receipt, PO, etc.)
- extraction/      — Extracts type-specific fields from OCR text
- validation/      — Applies business rules and field validation
- confidence/      — Computes per-field and document-level confidence scores
- review/          — Routes documents to human review or auto-approval

Agents are pure functions of their inputs — they do not directly access
the database. Persistence is handled by the service/activity layer.
"""
