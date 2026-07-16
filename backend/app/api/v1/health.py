"""Health, readiness and liveness probes."""

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import AppSettings
from app.infrastructure.database.session import get_session_factory

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health(settings: AppSettings) -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/live")
async def liveness() -> dict:
    return {"status": "alive"}


@router.get("/ready")
async def readiness() -> dict:
    checks: dict[str, str] = {}
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    status = "ready" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
