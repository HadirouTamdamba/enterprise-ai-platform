"""Prompt Registry endpoints (F-14..F-16): versioned prompts decoupled from code."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, require_role
from app.api.v1.schemas import (
    PromptCreate,
    PromptResponse,
    PromptVersionCreate,
    PromptVersionResponse,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.entities.identity import Role
from app.infrastructure.database.models import PromptModel, PromptVersionModel
from app.infrastructure.database.repositories.ai import AuditRepository, PromptRepository

router = APIRouter(prefix="/prompts", tags=["prompt-registry"])


@router.post("", response_model=PromptResponse, status_code=201,
             dependencies=[require_role(Role.ENGINEER)])
async def create_prompt(
    body: PromptCreate, session: DbSession, actor: CurrentUser
) -> PromptResponse:
    repo = PromptRepository(session)
    existing = await repo.list(project_id=body.project_id, name=body.name)
    if existing:
        raise ConflictError(f"Prompt '{body.name}' already exists in this project")
    prompt = await repo.add(
        PromptModel(
            name=body.name, description=body.description,
            tags=body.tags, project_id=body.project_id,
        )
    )
    version = PromptVersionModel(
        prompt_id=prompt.id, version=1, template=body.template,
        variables=body.variables, model_hint=body.model_hint,
        changelog="Initial version", is_active=True,
    )
    session.add(version)
    await AuditRepository(session).append(
        actor_id=actor.id, action="prompt.created", resource_type="prompt",
        resource_id=str(prompt.id),
    )
    return PromptResponse.model_validate(prompt)


@router.get("", response_model=list[PromptResponse], dependencies=[require_role(Role.VIEWER)])
async def list_prompts(
    session: DbSession, project_id: UUID | None = None
) -> list[PromptResponse]:
    prompts = await PromptRepository(session).list(project_id=project_id, limit=200)
    return [PromptResponse.model_validate(p) for p in prompts]


@router.get("/{prompt_id}/versions", response_model=list[PromptVersionResponse],
            dependencies=[require_role(Role.VIEWER)])
async def list_versions(prompt_id: UUID, session: DbSession) -> list[PromptVersionResponse]:
    return [
        PromptVersionResponse.model_validate(v)
        for v in await PromptRepository(session).versions(prompt_id)
    ]


@router.post("/{prompt_id}/versions", response_model=PromptVersionResponse, status_code=201,
             dependencies=[require_role(Role.ENGINEER)])
async def create_version(
    prompt_id: UUID, body: PromptVersionCreate, session: DbSession, actor: CurrentUser
) -> PromptVersionResponse:
    repo = PromptRepository(session)
    await repo.get(prompt_id)  # 404 if missing
    latest = await repo.latest_version(prompt_id)
    next_number = (latest.version + 1) if latest else 1
    if body.activate:
        await repo.deactivate_versions(prompt_id)
    version = PromptVersionModel(
        prompt_id=prompt_id, version=next_number, template=body.template,
        variables=body.variables, model_hint=body.model_hint,
        changelog=body.changelog, is_active=body.activate,
    )
    session.add(version)
    await session.flush()
    await AuditRepository(session).append(
        actor_id=actor.id, action="prompt.version_created", resource_type="prompt",
        resource_id=str(prompt_id), details={"version": next_number},
    )
    return PromptVersionResponse.model_validate(version)


@router.post("/{prompt_id}/versions/{version}/activate",
             response_model=PromptVersionResponse,
             dependencies=[require_role(Role.ENGINEER)])
async def activate_version(
    prompt_id: UUID, version: int, session: DbSession, actor: CurrentUser
) -> PromptVersionResponse:
    """Instant rollback/rollforward between prompt versions."""
    repo = PromptRepository(session)
    versions = await repo.versions(prompt_id)
    target = next((v for v in versions if v.version == version), None)
    if target is None:
        raise NotFoundError(f"Version {version} not found for prompt {prompt_id}")
    await repo.deactivate_versions(prompt_id)
    target.is_active = True
    await AuditRepository(session).append(
        actor_id=actor.id, action="prompt.version_activated", resource_type="prompt",
        resource_id=str(prompt_id), details={"version": version},
    )
    return PromptVersionResponse.model_validate(target)
