"""v1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1 import (
    agents,
    auth,
    gateway,
    governance,
    health,
    identity,
    monitoring,
    prompts,
    rag,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(identity.router)
api_router.include_router(gateway.router)
api_router.include_router(prompts.router)
api_router.include_router(rag.router)
api_router.include_router(agents.router)
api_router.include_router(governance.router)
api_router.include_router(monitoring.router)
