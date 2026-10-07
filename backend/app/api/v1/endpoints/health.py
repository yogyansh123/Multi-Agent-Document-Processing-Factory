"""
api/v1/endpoints/health.py
==========================
Health check and dependency readiness endpoints.

Provides:
- Liveness check (`GET /health`) for load balancers and container runtimes.
- Dependency readiness check (`GET /health?dependencies=true` or `GET /health/dependencies`)
  reporting live status for PostgreSQL, Redis, and Temporal.
- Distinguishes:
  - `healthy`: all services operational.
  - `degraded`: core application and database operational, but optional dependency is unavailable.
  - `unavailable`: core database is down.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db.session import get_session_maker
from app.services.cache import get_redis_service
from app.services.temporal.client import get_temporal_client

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Response schema for the health check endpoint."""

    status: str
    dependencies: dict[str, str] | None = Field(
        default=None,
        description="Health status of external dependencies (postgresql, redis, temporal).",
    )


async def check_all_dependencies() -> tuple[str, dict[str, str]]:
    """
    Query PostgreSQL, Redis, and Temporal dependencies.
    Returns (overall_status, dependencies_dict).
    """
    deps: dict[str, str] = {
        "postgresql": "unavailable",
        "redis": "unavailable",
        "temporal": "unavailable",
    }

    # 1. PostgreSQL check
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            await session.execute(text("SELECT 1"))
            deps["postgresql"] = "healthy"
    except Exception:
        deps["postgresql"] = "unavailable"

    # 2. Redis check
    try:
        redis_service = await get_redis_service()
        if await redis_service.is_healthy():
            deps["redis"] = "healthy"
        else:
            deps["redis"] = "unavailable"
    except Exception:
        deps["redis"] = "unavailable"

    # 3. Temporal check
    try:
        temporal_service = await get_temporal_client()
        if await temporal_service.is_healthy():
            deps["temporal"] = "healthy"
        else:
            deps["temporal"] = "unavailable"
    except Exception:
        deps["temporal"] = "unavailable"

    # Overall status:
    # If primary database is unavailable, application is unavailable.
    # If database is healthy but redis or temporal is down, application is degraded.
    # If all three are healthy, application is healthy.
    if deps["postgresql"] == "unavailable":
        overall = "unavailable"
    elif deps["redis"] == "unavailable" or deps["temporal"] == "unavailable":
        overall = "degraded"
    else:
        overall = "healthy"

    return overall, deps


@router.get(
    "/health",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    summary="Application health check",
    description=(
        "Returns basic liveness by default (`{'status': 'healthy'}`). "
        "Pass `?dependencies=true` to inspect PostgreSQL, Redis, and Temporal dependency status."
    ),
    operation_id="health_check",
)
async def health_check(
    dependencies: bool = Query(
        default=False,
        description="Include health status of external dependencies",
    ),
) -> HealthResponse:
    """
    Liveness and dependency readiness health check.
    """
    if not dependencies:
        return HealthResponse(status="healthy")

    overall, deps = await check_all_dependencies()
    return HealthResponse(status=overall, dependencies=deps)


@router.get(
    "/health/dependencies",
    response_model=HealthResponse,
    summary="Dependency health check",
    description="Inspects PostgreSQL, Redis, and Temporal dependency status.",
    operation_id="health_dependencies_check",
)
@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness health check",
    description="Inspects PostgreSQL, Redis, and Temporal dependency status.",
    operation_id="readiness_check",
)
async def health_dependencies_check() -> HealthResponse:
    """
    Always return dependency statuses.
    """
    overall, deps = await check_all_dependencies()
    return HealthResponse(status=overall, dependencies=deps)
