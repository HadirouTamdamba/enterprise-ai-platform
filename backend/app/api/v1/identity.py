"""User, organization, workspace and project management endpoints."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, require_role
from app.api.v1.schemas import (
    OrganizationCreate,
    OrganizationResponse,
    ProjectCreate,
    ProjectResponse,
    UserResponse,
    UserUpdateRequest,
    WorkspaceCreate,
    WorkspaceResponse,
)
from app.core.exceptions import ConflictError
from app.domain.entities.identity import Role
from app.infrastructure.database.models import (
    OrganizationModel,
    ProjectModel,
    WorkspaceModel,
)
from app.infrastructure.database.repositories.ai import AuditRepository
from app.infrastructure.database.repositories.identity import (
    OrganizationRepository,
    ProjectRepository,
    UserRepository,
    WorkspaceRepository,
)

router = APIRouter(tags=["identity"])


# ---------- Users ----------
@router.get("/users", response_model=list[UserResponse],
            dependencies=[require_role(Role.ORG_ADMIN)])
async def list_users(session: DbSession, limit: int = 50, offset: int = 0) -> list[UserResponse]:
    users = await UserRepository(session).list(limit=limit, offset=offset)
    return [UserResponse.model_validate(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserResponse,
              dependencies=[require_role(Role.ORG_ADMIN)])
async def update_user(
    user_id: UUID, body: UserUpdateRequest, session: DbSession, actor: CurrentUser
) -> UserResponse:
    repo = UserRepository(session)
    user = await repo.get(user_id)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(user, field, value.value if isinstance(value, Role) else value)
    await AuditRepository(session).append(
        actor_id=actor.id, action="user.updated", resource_type="user",
        resource_id=str(user_id), details={"changes": list(changes)},
    )
    return UserResponse.model_validate(user)


# ---------- Organizations ----------
@router.post("/organizations", response_model=OrganizationResponse, status_code=201,
             dependencies=[require_role(Role.PLATFORM_ADMIN)])
async def create_organization(
    body: OrganizationCreate, session: DbSession, actor: CurrentUser
) -> OrganizationResponse:
    repo = OrganizationRepository(session)
    if await repo.find_by_slug(body.slug):
        raise ConflictError(f"Organization slug '{body.slug}' already exists")
    org = await repo.add(OrganizationModel(**body.model_dump()))
    await AuditRepository(session).append(
        actor_id=actor.id, action="organization.created", resource_type="organization",
        resource_id=str(org.id),
    )
    return OrganizationResponse.model_validate(org)


@router.get("/organizations", response_model=list[OrganizationResponse],
            dependencies=[require_role(Role.VIEWER)])
async def list_organizations(session: DbSession) -> list[OrganizationResponse]:
    orgs = await OrganizationRepository(session).list(limit=100)
    return [OrganizationResponse.model_validate(o) for o in orgs]


# ---------- Workspaces ----------
@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201,
             dependencies=[require_role(Role.ORG_ADMIN)])
async def create_workspace(
    body: WorkspaceCreate, session: DbSession, actor: CurrentUser
) -> WorkspaceResponse:
    await OrganizationRepository(session).get(body.organization_id)  # 404 if missing
    ws = await WorkspaceRepository(session).add(WorkspaceModel(**body.model_dump()))
    await AuditRepository(session).append(
        actor_id=actor.id, action="workspace.created", resource_type="workspace",
        resource_id=str(ws.id),
    )
    return WorkspaceResponse.model_validate(ws)


@router.get("/workspaces", response_model=list[WorkspaceResponse],
            dependencies=[require_role(Role.VIEWER)])
async def list_workspaces(
    session: DbSession, organization_id: UUID | None = None
) -> list[WorkspaceResponse]:
    items = await WorkspaceRepository(session).list(organization_id=organization_id)
    return [WorkspaceResponse.model_validate(w) for w in items]


# ---------- Projects ----------
@router.post("/projects", response_model=ProjectResponse, status_code=201,
             dependencies=[require_role(Role.ENGINEER)])
async def create_project(
    body: ProjectCreate, session: DbSession, actor: CurrentUser
) -> ProjectResponse:
    await WorkspaceRepository(session).get(body.workspace_id)
    project = await ProjectRepository(session).add(ProjectModel(**body.model_dump()))
    await AuditRepository(session).append(
        actor_id=actor.id, action="project.created", resource_type="project",
        resource_id=str(project.id),
    )
    return ProjectResponse.model_validate(project)


@router.get("/projects", response_model=list[ProjectResponse],
            dependencies=[require_role(Role.VIEWER)])
async def list_projects(
    session: DbSession, workspace_id: UUID | None = None
) -> list[ProjectResponse]:
    items = await ProjectRepository(session).list(workspace_id=workspace_id)
    return [ProjectResponse.model_validate(p) for p in items]


@router.get("/projects/{project_id}", response_model=ProjectResponse,
            dependencies=[require_role(Role.VIEWER)])
async def get_project(project_id: UUID, session: DbSession) -> ProjectResponse:
    return ProjectResponse.model_validate(await ProjectRepository(session).get(project_id))
