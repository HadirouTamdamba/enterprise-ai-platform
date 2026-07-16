"""FastAPI dependencies: DB session, current user, RBAC guards, rate limiting."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthorizationError, RateLimitExceededError
from app.core.logging import user_id_var
from app.core.security import decode_token
from app.domain.entities.identity import Role, role_at_least
from app.infrastructure.cache.rate_limiter import RateLimiter, get_rate_limiter
from app.infrastructure.database.models import UserModel
from app.infrastructure.database.repositories.identity import UserRepository
from app.infrastructure.database.session import get_db_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: DbSession
) -> UserModel:
    payload = decode_token(token, expected_type="access")
    user = await UserRepository(session).get(UUID(payload["sub"]))
    if not user.is_active:
        raise AuthorizationError("Account is deactivated")
    user_id_var.set(str(user.id))
    return user


CurrentUser = Annotated[UserModel, Depends(get_current_user)]


def require_role(minimum: Role):
    """Route guard: current user must hold at least `minimum` role."""

    async def guard(user: CurrentUser) -> UserModel:
        if not role_at_least(Role(user.role), minimum):
            raise AuthorizationError(f"Requires role '{minimum.value}' or higher")
        return user

    return Depends(guard)


async def enforce_rate_limit(
    request: Request,
    user: CurrentUser,
    settings: AppSettings,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    allowed = await limiter.check(
        key=f"rl:req:{user.id}",
        limit=settings.rate_limit_requests_per_minute,
        window_seconds=60,
    )
    if not allowed:
        raise RateLimitExceededError("Request rate limit exceeded — retry later")
