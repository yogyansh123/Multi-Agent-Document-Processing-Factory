"""
tests/test_health_dependencies.py
==================================
Tests for extended health infrastructure and dependency status reporting:
- Liveness check (GET /health) returns basic status
- Dependency check (GET /health?dependencies=true, GET /health/dependencies, GET /health/ready)
- Healthy status when all dependencies are healthy
- Degraded status when Redis or Temporal is unavailable
- Unavailable status when PostgreSQL is down
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from app.services.cache import RedisService, set_redis_service
from app.services.temporal.client import TemporalClientService, set_temporal_client


@pytest.mark.asyncio
async def test_basic_health_check_returns_simple_status(async_client: AsyncClient):
    """Liveness check without parameters returns status healthy."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_health_with_dependencies_all_healthy(async_client: AsyncClient):
    """When DB, Redis, and Temporal are available, status is healthy."""
    # Ensure mock redis and temporal report healthy
    mock_redis = RedisService(client=None, is_mock=True)
    mock_temporal = TemporalClientService(client=None, is_mock=True)

    set_redis_service(mock_redis)
    set_temporal_client(mock_temporal)

    response = await async_client.get("/health?dependencies=true")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert "dependencies" in data
    assert data["dependencies"]["postgresql"] == "healthy"
    assert data["dependencies"]["redis"] == "healthy"
    assert data["dependencies"]["temporal"] == "healthy"


@pytest.mark.asyncio
async def test_health_ready_endpoint(async_client: AsyncClient):
    """GET /health/ready always returns dependency statuses."""
    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert "dependencies" in data
    assert "postgresql" in data["dependencies"]
    assert "redis" in data["dependencies"]
    assert "temporal" in data["dependencies"]


@pytest.mark.asyncio
async def test_health_degraded_when_redis_unavailable(async_client: AsyncClient):
    """When Redis is down but PostgreSQL is up, overall status is degraded."""
    class FailingRedis:
        async def ping(self):
            return False

    unhealthy_redis = RedisService(client=FailingRedis(), is_mock=False)
    set_redis_service(unhealthy_redis)

    try:
        response = await async_client.get("/health/dependencies")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert data["dependencies"]["postgresql"] == "healthy"
        assert data["dependencies"]["redis"] == "unavailable"
    finally:
        # Reset back to mock
        set_redis_service(RedisService(client=None, is_mock=True))


@pytest.mark.asyncio
async def test_health_degraded_when_temporal_unavailable(async_client: AsyncClient):
    """When Temporal is down but PostgreSQL is up, overall status is degraded."""
    unhealthy_temporal = TemporalClientService(client=None, is_mock=False)
    set_temporal_client(unhealthy_temporal)

    try:
        response = await async_client.get("/health/dependencies")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert data["dependencies"]["postgresql"] == "healthy"
        assert data["dependencies"]["temporal"] == "unavailable"
    finally:
        # Reset back to mock
        set_temporal_client(TemporalClientService(client=None, is_mock=True))


@pytest.mark.asyncio
async def test_health_unavailable_when_postgresql_fails(async_client: AsyncClient):
    """When primary database connection fails, overall status is unavailable."""
    with patch("app.api.v1.endpoints.health.get_session_maker") as mock_sm:
        # Mock session that raises
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("DB connection refused")
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_sm.return_value = lambda: mock_context

        response = await async_client.get("/health/dependencies")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "unavailable"
        assert data["dependencies"]["postgresql"] == "unavailable"


# ---------------------------------------------------------------------------
# Database Engine URL Parsing & asyncpg Compatibility Regression Tests
# ---------------------------------------------------------------------------


def test_prepare_engine_args_neon_sslmode_require():
    """Verify Neon PostgreSQL URL with sslmode=require converts to asyncpg connect_args."""
    from app.db.session import prepare_engine_args
    from sqlalchemy.engine.url import URL

    neon_url = "postgresql://user:password@ep-cool-fog-123.us-east-2.aws.neon.tech/neondb?sslmode=require"
    url, kwargs = prepare_engine_args(neon_url)

    assert isinstance(url, URL)
    assert url.drivername == "postgresql+asyncpg"
    assert "sslmode" not in url.query
    assert kwargs.get("connect_args") == {"ssl": "require"}
    assert kwargs.get("pool_size") == 10
    assert kwargs.get("pool_pre_ping") is not True or kwargs.get("pool_size") == 10


def test_prepare_engine_args_neon_with_channel_binding():
    """Verify channel_binding and sslmode are both safely stripped for asyncpg."""
    from app.db.session import prepare_engine_args

    url_str = "postgresql+asyncpg://user:pass@ep-cool.neon.tech/neondb?sslmode=require&channel_binding=require"
    url, kwargs = prepare_engine_args(url_str)

    assert "sslmode" not in url.query
    assert "channel_binding" not in url.query
    assert kwargs.get("connect_args") == {"ssl": "require"}


def test_prepare_engine_args_various_sslmodes():
    """Verify other standard sslmodes map accurately to asyncpg ssl strings."""
    from app.db.session import prepare_engine_args

    for mode in ("verify-full", "verify-ca", "prefer", "disable", "allow"):
        url_str = f"postgresql://user:pass@ep-cool.neon.tech/neondb?sslmode={mode}"
        url, kwargs = prepare_engine_args(url_str)
        assert "sslmode" not in url.query
        assert kwargs.get("connect_args") == {"ssl": mode}


def test_prepare_engine_args_local_postgres_url():
    """Verify local PostgreSQL development URLs retain standard settings without ssl."""
    from app.db.session import prepare_engine_args

    local_url = "postgresql+asyncpg://docfactory:changeme@localhost:5432/document_factory"
    url, kwargs = prepare_engine_args(local_url)

    assert url.drivername == "postgresql+asyncpg"
    assert kwargs.get("connect_args") is None or "ssl" not in kwargs.get("connect_args", {})
    assert kwargs.get("pool_size") == 10


def test_prepare_engine_args_sqlite_url():
    """Verify in-memory SQLite used in testing is not altered or given pool kwargs."""
    from app.db.session import prepare_engine_args

    sqlite_url = "sqlite+aiosqlite:///:memory:"
    url, kwargs = prepare_engine_args(sqlite_url)

    assert url.drivername == "sqlite+aiosqlite"
    assert "pool_size" not in kwargs
    assert kwargs.get("connect_args") is None

