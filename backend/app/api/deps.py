"""
api/deps.py
===========
FastAPI dependency injection helpers.

This module defines reusable `Depends(...)` dependencies for:
- Database sessions
- Storage provider
- Future: authentication / authorisation
- Future: pagination parameters
- Future: rate limiting

Keep this module lightweight — it is imported by every endpoint.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.ocr.base import OCRProvider
from app.services.ocr.factory import get_ocr_provider
from app.services.llm.base import LLMProvider
from app.services.llm.factory import get_llm_provider
from app.services.storage.base import StorageProvider
from app.services.storage.factory import get_storage_provider

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
"""
Type alias for injecting an async SQLAlchemy session into route handlers.

Usage:
    @router.get("/example")
    async def example(db: DbSession) -> ...:
        result = await db.execute(...)
"""

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

Storage = Annotated[StorageProvider, Depends(get_storage_provider)]
"""
Type alias for injecting the configured storage provider.

Usage:
    @router.post("/upload")
    async def upload(storage: Storage) -> ...:
        stored = await storage.save(...)
"""

# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

Ocr = Annotated[OCRProvider, Depends(get_ocr_provider)]
"""
Type alias for injecting the configured OCR provider.

Usage:
    @router.post("/{document_id}/ocr")
    async def trigger_ocr(ocr: Ocr) -> ...:
        ...
"""

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

Llm = Annotated[LLMProvider, Depends(get_llm_provider)]
"""
Type alias for injecting the configured LLM provider.

Usage:
    @router.post("/{document_id}/classify")
    async def classify(llm: Llm) -> ...:
        ...
"""

# ---------------------------------------------------------------------------
# Temporal
# ---------------------------------------------------------------------------

from app.services.temporal.client import TemporalClientService, get_temporal_client

Temporal = Annotated[TemporalClientService, Depends(get_temporal_client)]
"""
Type alias for injecting the Temporal client service.

Usage:
    @router.post("/{document_id}/process")
    async def process(temporal: Temporal) -> ...:
        ...
"""

# ---------------------------------------------------------------------------
# Cache (Redis)
# ---------------------------------------------------------------------------

from app.services.cache import RedisService, get_redis_service

Cache = Annotated[RedisService, Depends(get_redis_service)]
"""
Type alias for injecting the Redis cache service.

Usage:
    @router.get("/{document_id}/processing-status")
    async def get_status(cache: Cache) -> ...:
        ...
"""


