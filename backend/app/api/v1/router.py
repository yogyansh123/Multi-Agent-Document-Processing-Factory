"""
api/v1/router.py
================
Top-level API v1 router.

All versioned API endpoints are registered here.  The prefix `/api/v1`
is applied by the main application when including this router.

To add a new resource:
    1. Create `api/v1/endpoints/your_resource.py`
    2. Import its router below
    3. Add an `api_router.include_router(...)` call
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    analytics,
    classification,
    confidence,
    documents,
    extraction,
    health,
    ocr,
    rag,
    review,
    validation,
    workflows,
)

api_router = APIRouter()

# Health check — also mounted at root level by main.py
api_router.include_router(health.router)

# Documents
api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents"],
)

# OCR (sub-routes of /documents: /{id}/ocr, /{id}/text)
api_router.include_router(
    ocr.router,
    prefix="/documents",
    tags=["OCR"],
)

# Classification (sub-routes of /documents: /{id}/classify, /{id}/classification)
api_router.include_router(
    classification.router,
    prefix="/documents",
    tags=["Classification"],
)

# Extraction (sub-routes of /documents: /{id}/extract, /{id}/extraction)
api_router.include_router(
    extraction.router,
    prefix="/documents",
    tags=["Extraction"],
)

# Validation (sub-routes of /documents: /{id}/validate, /{id}/validation)
api_router.include_router(
    validation.router,
    prefix="/documents",
    tags=["Validation"],
)

# Confidence Scoring (sub-routes of /documents: /{id}/confidence)
api_router.include_router(
    confidence.router,
    prefix="/documents",
    tags=["Confidence"],
)

# Temporal Workflows (sub-routes of /documents: /{id}/process, /{id}/workflow)
api_router.include_router(
    workflows.router,
    prefix="/documents",
    tags=["Workflows"],
)

# Human-in-the-Loop Review
api_router.include_router(
    review.router,
    prefix="/review",
    tags=["Review"],
)

# RAG & Document Intelligence (/rag and /documents/{id}/index)
api_router.include_router(rag.rag_router)
api_router.include_router(rag.document_rag_router)

# Analytics & Processing Observability
api_router.include_router(analytics.router)





