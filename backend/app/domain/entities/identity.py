"""Identity & tenancy domain entities. Pure Python — no framework imports."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class Role(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    ORG_ADMIN = "org_admin"
    WORKSPACE_ADMIN = "workspace_admin"
    ENGINEER = "engineer"
    ANALYST = "analyst"
    COMPLIANCE_OFFICER = "compliance_officer"
    VIEWER = "viewer"


# Ordered by privilege; used for "at least role X" checks.
_ROLE_RANK: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.ANALYST: 1,
    Role.ENGINEER: 2,
    Role.COMPLIANCE_OFFICER: 2,
    Role.WORKSPACE_ADMIN: 3,
    Role.ORG_ADMIN: 4,
    Role.PLATFORM_ADMIN: 5,
}


def role_at_least(actual: Role, required: Role) -> bool:
    """Business rule: role hierarchy for authorization checks."""
    return _ROLE_RANK[actual] >= _ROLE_RANK[required]


@dataclass(slots=True)
class User:
    email: str
    full_name: str
    hashed_password: str
    role: Role = Role.VIEWER
    is_active: bool = True
    organization_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def can_manage(self, required: Role) -> bool:
        return self.is_active and role_at_least(self.role, required)


@dataclass(slots=True)
class Organization:
    name: str
    slug: str
    monthly_budget_usd: float = 0.0  # 0 = unlimited
    is_active: bool = True
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Workspace:
    name: str
    organization_id: UUID
    description: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def vector_collection(self) -> str:
        """Each workspace gets an isolated vector collection."""
        return f"ws_{self.id.hex}"


@dataclass(slots=True)
class Project:
    name: str
    workspace_id: UUID
    description: str = ""
    default_llm_provider: str | None = None
    default_llm_model: str | None = None
    monthly_budget_usd: float = 0.0
    is_active: bool = True
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
