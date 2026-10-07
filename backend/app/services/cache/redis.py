"""
services/cache/redis.py
=======================
Redis cache abstraction and document processing status caching.

Key responsibilities:
- Connection management with graceful degradation.
- Safe key generation (`document:status:{document_id}`).
- Document processing status caching with configurable TTL.
- Ping & health checks.
- Transparent fallback to PostgreSQL when Redis is unreachable or unconfigured.
- PostgreSQL remains the durable source of truth.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.services.cache")

try:
    import redis.asyncio as aioredis
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover
    aioredis = None  # type: ignore[assignment]
    RedisError = Exception  # type: ignore[misc,assignment]


class RedisService:
    """
    Asynchronous Redis cache service with resilient fallback.
    """

    def __init__(
        self,
        client: Any = None,
        is_mock: bool = False,
        default_ttl: int = 3600,
    ) -> None:
        self._client = client
        self._is_mock = is_mock
        self._default_ttl = default_ttl
        # In-memory store for mock mode: key -> (serialized_str, expire_timestamp_epoch)
        self._mock_store: dict[str, tuple[str, float]] = {}

    @classmethod
    async def connect(cls, url: str | None = None) -> RedisService:
        """
        Create a connected RedisService instance.
        If connection cannot be established, logs a warning and returns an
        unavailable / mock fallback instance without crashing the application.
        """
        redis_url = url or settings.REDIS_URL
        ttl = settings.REDIS_STATUS_TTL_SECONDS

        if aioredis is None:
            logger.warning("redis.package_missing_fallback_mock")
            return cls(client=None, is_mock=True, default_ttl=ttl)

        try:
            client = aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            # Verify connectivity via ping
            await client.ping()
            logger.info("redis.connected", url=redis_url)
            return cls(client=client, is_mock=False, default_ttl=ttl)
        except Exception as exc:
            logger.warning(
                "redis.connection_failed_fallback",
                url=redis_url,
                error=str(exc),
                message="Continuing with in-memory fallback. PostgreSQL is source of truth.",
            )
            return cls(client=None, is_mock=True, default_ttl=ttl)

    # -------------------------------------------------------------------------
    # Key Generation
    # -------------------------------------------------------------------------
    @staticmethod
    def make_status_key(document_id: str | uuid.UUID) -> str:
        """
        Generate canonical status cache key.
        Format: document:status:{document_id}
        """
        doc_str = str(document_id).strip()
        return f"document:status:{doc_str}"

    # -------------------------------------------------------------------------
    # Health & Connectivity
    # -------------------------------------------------------------------------
    async def ping(self) -> bool:
        """
        Ping Redis server to determine live availability.
        Returns False gracefully on connection error.
        """
        if self._is_mock:
            # Mock mode behaves as available for in-memory operations
            return True
        if self._client is None:
            return False
        try:
            pong = await self._client.ping()
            return bool(pong)
        except Exception as exc:
            logger.debug("redis.ping_failed", error=str(exc))
            return False

    async def is_healthy(self) -> bool:
        """Check if Redis connection is healthy."""
        return await self.ping()

    # -------------------------------------------------------------------------
    # Serialization Helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def serialize_status(data: dict[str, Any]) -> str:
        """Serialize document processing status dictionary to JSON string."""
        serializable: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, uuid.UUID):
                serializable[k] = str(v)
            elif isinstance(v, datetime):
                serializable[k] = v.isoformat()
            else:
                serializable[k] = v
        return json.dumps(serializable, sort_keys=True)

    @staticmethod
    def deserialize_status(raw: str) -> dict[str, Any]:
        """Deserialize JSON string from cache into status dictionary."""
        return json.loads(raw)

    # -------------------------------------------------------------------------
    # Document Status Cache Operations
    # -------------------------------------------------------------------------
    async def get_document_status(
        self,
        document_id: str | uuid.UUID,
    ) -> dict[str, Any] | None:
        """
        Retrieve cached document processing status.
        Returns None on cache miss, expiration, or Redis failure.
        """
        key = self.make_status_key(document_id)

        # Mock / In-memory path
        if self._is_mock or self._client is None:
            entry = self._mock_store.get(key)
            if entry is None:
                return None
            raw, expire_at = entry
            if time.time() > expire_at:
                self._mock_store.pop(key, None)
                return None
            try:
                return self.deserialize_status(raw)
            except Exception as exc:
                logger.warning("redis.mock_deserialization_error", key=key, error=str(exc))
                return None

        # Real Redis path
        try:
            raw_val = await self._client.get(key)
            if raw_val is None:
                return None
            return self.deserialize_status(raw_val)
        except Exception as exc:
            logger.warning(
                "redis.get_failed_fallback_to_postgres",
                key=key,
                error=str(exc),
            )
            return None

    async def set_document_status(
        self,
        document_id: str | uuid.UUID,
        data: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> bool:
        """
        Store document processing status in cache.
        Returns True on success, False if Redis is unavailable (safe no-op).
        """
        key = self.make_status_key(document_id)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        raw_val = self.serialize_status(data)

        # Mock / In-memory path
        if self._is_mock or self._client is None:
            expire_at = time.time() + ttl
            self._mock_store[key] = (raw_val, expire_at)
            return True

        # Real Redis path
        try:
            await self._client.set(key, raw_val, ex=ttl)
            return True
        except Exception as exc:
            logger.warning(
                "redis.set_failed",
                key=key,
                error=str(exc),
            )
            return False

    async def delete_document_status(self, document_id: str | uuid.UUID) -> bool:
        """
        Invalidate cached status for a document.
        """
        key = self.make_status_key(document_id)

        if self._is_mock or self._client is None:
            self._mock_store.pop(key, None)
            return True

        try:
            await self._client.delete(key)
            return True
        except Exception as exc:
            logger.warning("redis.delete_failed", key=key, error=str(exc))
            return False

    async def close(self) -> None:
        """Gracefully close Redis connection pool."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception as exc:
                logger.debug("redis.close_error", error=str(exc))
