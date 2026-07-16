"""v1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1 import auth, health, identity

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(identity.router)
