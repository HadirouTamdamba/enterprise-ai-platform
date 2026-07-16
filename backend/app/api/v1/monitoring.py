"""Monitoring Center (F-55): usage, cost and latency analytics for dashboards."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession, require_role
from app.domain.entities.identity import Role
from app.infrastructure.database.repositories.ai import UsageRepository

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _since(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


@router.get("/usage", dependencies=[require_role(Role.VIEWER)])
async def usage_summary(
    session: DbSession, project_id: UUID | None = None, days: int = 30
) -> dict:
    repo = UsageRepository(session)
    totals = await repo.totals(project_id=project_id, since=_since(min(days, 365)))
    return {"window_days": days, "project_id": str(project_id) if project_id else None, **totals}


@router.get("/usage/by-model", dependencies=[require_role(Role.VIEWER)])
async def usage_by_model(session: DbSession, days: int = 30) -> list[dict]:
    return await UsageRepository(session).by_model(since=_since(min(days, 365)))


@router.get("/costs", dependencies=[require_role(Role.ANALYST)])
async def cost_dashboard(session: DbSession, days: int = 30) -> dict:
    """Cost analytics (F-11): totals + per-model breakdown for budget tracking."""
    repo = UsageRepository(session)
    since = _since(min(days, 365))
    totals = await repo.totals(since=since)
    per_model = await repo.by_model(since=since)
    return {
        "window_days": days,
        "total_cost_usd": totals["cost_usd"],
        "total_requests": totals["requests"],
        "avg_latency_ms": totals["avg_latency_ms"],
        "by_model": sorted(per_model, key=lambda m: m["cost_usd"], reverse=True),
    }
