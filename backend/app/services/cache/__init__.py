"""
services/cache/__init__.py
==========================
Cache service package initialization.
"""

from __future__ import annotations

from typing import Optional
from app.services.cache.redis import RedisService

_global_redis_service: Optional[RedisService] = None


async def get_redis_service() -> RedisService:
    """
    Return or lazily initialize the singleton RedisService instance.
    """
    global _global_redis_service
    if _global_redis_service is None:
        _global_redis_service = await RedisService.connect()
    return _global_redis_service


def set_redis_service(service: Optional[RedisService]) -> None:
    """
    Override RedisService instance (for testing).
    """
    global _global_redis_service
    _global_redis_service = service


__all__ = [
    "RedisService",
    "get_redis_service",
    "set_redis_service",
]
