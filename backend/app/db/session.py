"""
db/session.py
=============
Async SQLAlchemy engine and session factory.

This module provides:
- `get_async_engine()`: lazily creates and caches the async engine.
- `AsyncSessionLocal`: a session factory for creating database sessions.
- `get_db_session()`: an async generator for FastAPI dependency injection.

The engine is created lazily (on first use) so that tests can override the
database URL via environment variables before the engine is constructed.
No credentials are hardcoded here.

Usage:
    # In a FastAPI dependency (preferred):
    from app.db.session import get_db_session
    from sqlalchemy.ext.asyncio import AsyncSession

    async def some_endpoint(db: AsyncSession = Depends(get_db_session)):
        result = await db.execute(select(SomeModel))

    # As a context manager in service code:
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        ...
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    """
    Build and cache the async SQLAlchemy engine.

    Created lazily on first call so tests can configure the database URL
    via environment variables before this runs.
    """
    engine_kwargs: dict = {
        "echo": settings.DEBUG,
        "pool_pre_ping": True,
    }

    # SQLite (used in tests) does not support connection pool configuration
    if not settings.DATABASE_URL.startswith("sqlite"):
        engine_kwargs.update(
            {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 1800,
            }
        )

    return create_async_engine(settings.DATABASE_URL, **engine_kwargs)


# Backwards-compatible alias so existing code that does
# `from app.db.session import async_engine` still works.
@property  # type: ignore[misc]
def async_engine() -> AsyncEngine:  # type: ignore[misc]
    return get_async_engine()


_custom_session_maker: async_sessionmaker[AsyncSession] | None = None


def set_session_maker(maker: async_sessionmaker[AsyncSession] | None) -> None:
    """Override session maker for background activities in testing."""
    global _custom_session_maker
    _custom_session_maker = maker


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    if _custom_session_maker is not None:
        return _custom_session_maker
    return async_sessionmaker(
        bind=get_async_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


_get_session_maker = get_session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.

    Automatically commits on success and rolls back on exception.
    Always closes the session when the request is complete.
    """
    session_maker = _get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection() -> bool:
    """
    Verify that the database is reachable.

    Used during application startup and health checks.

    Returns
    -------
    True if the database connection succeeds, False otherwise.
    """
    from sqlalchemy import text

    try:
        engine = get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("database.connection.ok", url=settings.POSTGRES_HOST)
        return True
    except Exception as exc:
        logger.error("database.connection.failed", error=str(exc))
        return False
