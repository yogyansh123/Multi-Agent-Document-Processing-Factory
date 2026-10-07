"""
db/init_db.py
=============
Database initialisation utilities for development.

In development, this module creates tables that do not yet exist via
SQLAlchemy's `create_all()`.  It does NOT drop or modify existing tables,
making it safe to run repeatedly.

In production, use Alembic migrations instead:
    alembic upgrade head

Usage (called during app startup in development):
    from app.db.init_db import init_db
    await init_db()
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.db.base import Base
from app.db.session import get_async_engine

# Import all models so they are registered with Base.metadata before create_all
import app.models  # noqa: F401 — side-effect import, do not remove

logger = get_logger(__name__)


async def init_db() -> None:
    """
    Create all database tables that do not already exist.

    Safe to call on every startup:
    - Uses CREATE TABLE IF NOT EXISTS semantics (checkfirst=True).
    - Never drops or alters existing tables.
    - Should only be used in development; use Alembic in production.
    """
    async with get_async_engine().begin() as conn:
        logger.info("db.init.start", message="Creating missing tables...")
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        logger.info("db.init.complete", message="Database tables are ready.")
