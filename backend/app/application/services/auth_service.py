"""Authentication use cases: register, login, refresh."""

from uuid import UUID

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.domain.entities.identity import Role
from app.infrastructure.database.models import UserModel
from app.infrastructure.database.repositories.ai import AuditRepository
from app.infrastructure.database.repositories.identity import UserRepository


class AuthService:
    def __init__(self, users: UserRepository, audit: AuditRepository) -> None:
        self._users = users
        self._audit = audit

    async def register(
        self,
        *,
        email: str,
        full_name: str,
        password: str,
        role: Role = Role.VIEWER,
        organization_id: UUID | None = None,
    ) -> UserModel:
        if await self._users.find_by_email(email):
            raise ConflictError("A user with this email already exists")
        user = UserModel(
            email=email.lower(),
            full_name=full_name,
            hashed_password=hash_password(password),
            role=role.value,
            organization_id=organization_id,
        )
        await self._users.add(user)
        await self._audit.append(
            actor_id=user.id, action="user.registered", resource_type="user",
            resource_id=str(user.id),
        )
        return user

    async def login(self, *, email: str, password: str) -> tuple[str, str, UserModel]:
        user = await self._users.find_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            # Same error for both cases: never reveal which field failed.
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")
        access = create_token(user.id, "access", role=user.role)
        refresh = create_token(user.id, "refresh", role=user.role)
        await self._audit.append(
            actor_id=user.id, action="user.login", resource_type="user",
            resource_id=str(user.id),
        )
        return access, refresh, user

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        payload = decode_token(refresh_token, expected_type="refresh")
        user = await self._users.get(UUID(payload["sub"]))
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")
        return (
            create_token(user.id, "access", role=user.role),
            create_token(user.id, "refresh", role=user.role),
        )
