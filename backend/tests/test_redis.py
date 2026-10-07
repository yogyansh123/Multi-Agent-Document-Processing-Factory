"""
tests/test_redis.py
===================
Tests for Redis cache service:
- Key generation
- Serialization and deserialization
- Cache set and get operations
- TTL expiration
- Graceful fallback when Redis is unavailable
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
import pytest

from app.services.cache.redis import RedisService


def test_redis_key_generation():
    """Verify key generation matches document:status:{document_id} format."""
    test_uuid = uuid.uuid4()
    key = RedisService.make_status_key(test_uuid)
    assert key == f"document:status:{test_uuid}"

    str_id = "doc-custom-123"
    key2 = RedisService.make_status_key(str_id)
    assert key2 == "document:status:doc-custom-123"


def test_redis_serialization_deserialization():
    """Verify serialization and deserialization preserve datatypes correctly."""
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "document_id": doc_id,
        "status": "APPROVED",
        "current_stage": "CONFIDENCE_SCORING",
        "workflow_id": f"document-processing-{doc_id}",
        "overall_confidence": 0.945,
        "confidence_recommendation": "APPROVED",
        "started_at": now,
        "updated_at": now,
        "completed_at": now,
        "failed_stage": None,
        "error_message": None,
    }

    serialized = RedisService.serialize_status(payload)
    assert isinstance(serialized, str)
    assert doc_id in serialized
    assert "0.945" in serialized

    deserialized = RedisService.deserialize_status(serialized)
    assert deserialized["document_id"] == doc_id
    assert deserialized["status"] == "APPROVED"
    assert deserialized["overall_confidence"] == 0.945
    assert deserialized["started_at"] == now.isoformat()
    assert deserialized["failed_stage"] is None


@pytest.mark.asyncio
async def test_redis_cache_set_and_get():
    """Verify in-memory/mock cache set and get operations."""
    service = RedisService(client=None, is_mock=True, default_ttl=3600)
    doc_id = str(uuid.uuid4())
    payload = {
        "document_id": doc_id,
        "status": "PROCESSING",
        "current_stage": "EXTRACTION",
        "workflow_id": f"document-processing-{doc_id}",
        "overall_confidence": None,
        "confidence_recommendation": None,
    }

    # Cache miss
    miss = await service.get_document_status(doc_id)
    assert miss is None

    # Cache set
    success = await service.set_document_status(doc_id, payload)
    assert success is True

    # Cache hit
    hit = await service.get_document_status(doc_id)
    assert hit is not None
    assert hit["document_id"] == doc_id
    assert hit["status"] == "PROCESSING"
    assert hit["current_stage"] == "EXTRACTION"


@pytest.mark.asyncio
async def test_redis_ttl_expiration():
    """Verify that cached entries expire after TTL."""
    # Set short TTL of 1 second
    service = RedisService(client=None, is_mock=True, default_ttl=1)
    doc_id = str(uuid.uuid4())
    payload = {"document_id": doc_id, "status": "UPLOADED"}

    await service.set_document_status(doc_id, payload, ttl_seconds=1)

    # Immediately available
    cached = await service.get_document_status(doc_id)
    assert cached is not None
    assert cached["status"] == "UPLOADED"

    # Simulate TTL expiration by manipulating expire_at
    key = service.make_status_key(doc_id)
    raw_val, _ = service._mock_store[key]
    service._mock_store[key] = (raw_val, time.time() - 10)

    # After expiration, returns None
    expired = await service.get_document_status(doc_id)
    assert expired is None


@pytest.mark.asyncio
async def test_redis_unavailable_fallback():
    """Verify that when Redis is completely unavailable, operations fail gracefully without crashing."""
    # Client that raises on operations
    class FailingRedisClient:
        async def ping(self):
            raise ConnectionError("Redis server unavailable")

        async def get(self, key):
            raise ConnectionError("Redis server unavailable")

        async def set(self, key, value, ex=None):
            raise ConnectionError("Redis server unavailable")

        async def delete(self, key):
            raise ConnectionError("Redis server unavailable")

    failing_service = RedisService(client=FailingRedisClient(), is_mock=False)

    # Ping returns False
    is_healthy = await failing_service.is_healthy()
    assert is_healthy is False

    # Get returns None gracefully
    doc_id = str(uuid.uuid4())
    status = await failing_service.get_document_status(doc_id)
    assert status is None

    # Set returns False gracefully without raising
    saved = await failing_service.set_document_status(doc_id, {"status": "PROCESSING"})
    assert saved is False

    # Delete returns False gracefully without raising
    deleted = await failing_service.delete_document_status(doc_id)
    assert deleted is False
