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


# The "build ladder": a linear seniority for creating/managing resources.
# compliance_officer is deliberately OFF this ladder — it is an oversight role,
# not a builder. It sits at analyst level here (read + playground + agents) so it
# CANNOT create projects, KBs, models or prompts (which need ENGINEER).
_BUILD_RANK: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.ANALYST: 1,
    Role.COMPLIANCE_OFFICER: 1,
    Role.ENGINEER: 2,
    Role.WORKSPACE_ADMIN: 3,
    Role.ORG_ADMIN: 4,
    Role.PLATFORM_ADMIN: 5,
}

# Governance/oversight capability is orthogonal to the build ladder: only these
# roles may review approvals and read the audit trail — never an engineer.
# This is what makes separation of duties real rather than rank-based.
_GOVERNANCE_ROLES: frozenset[Role] = frozenset(
    {Role.COMPLIANCE_OFFICER, Role.ORG_ADMIN, Role.PLATFORM_ADMIN}
)


def role_at_least(actual: Role, required: Role) -> bool:
    """Authorization rule.

    Governance-gated endpoints (required == COMPLIANCE_OFFICER) are satisfied
    only by explicit oversight roles — an ENGINEER, however senior on the build
    ladder, can never approve. All other gates use the linear build ladder.
    """
    if required == Role.COMPLIANCE_OFFICER:
        return actual in _GOVERNANCE_ROLES
    return _BUILD_RANK[actual] >= _BUILD_RANK[required]


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
