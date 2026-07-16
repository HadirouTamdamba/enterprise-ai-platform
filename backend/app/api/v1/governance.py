"""Governance Center (F-40..F-54): model registry, approvals, risk register,
cards, audit trail and AI inventory."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, require_role
from app.api.v1.schemas import (
    ApprovalDecision,
    ApprovalRequestCreate,
    ApprovalResponse,
    AuditEventResponse,
    ModelRegister,
    ModelResponse,
)
from app.core.exceptions import ApprovalRequiredError, BusinessRuleViolation
from app.domain.entities.ai import ApprovalStatus, ModelStage, RiskLevel
from app.domain.entities.identity import Role
from app.infrastructure.database.models import ApprovalModel, RegisteredModelModel
from app.infrastructure.database.repositories.ai import (
    ApprovalRepository,
    AuditRepository,
    KnowledgeBaseRepository,
    ModelRegistryRepository,
    PromptRepository,
)

router = APIRouter(prefix="/governance", tags=["governance"])


# --------------------------------------------------------------- model registry
@router.post("/models", response_model=ModelResponse, status_code=201,
             dependencies=[require_role(Role.ENGINEER)])
async def register_model(
    body: ModelRegister, session: DbSession, actor: CurrentUser
) -> ModelResponse:
    model = await ModelRegistryRepository(session).add(
        RegisteredModelModel(**body.model_dump(), owner_id=actor.id)
    )
    await AuditRepository(session).append(
        actor_id=actor.id, action="model.registered", resource_type="model",
        resource_id=str(model.id), details={"name": body.name, "version": body.version},
    )
    return ModelResponse.model_validate(model)


@router.get("/models", response_model=list[ModelResponse],
            dependencies=[require_role(Role.VIEWER)])
async def list_models(
    session: DbSession, project_id: UUID | None = None, stage: str | None = None
) -> list[ModelResponse]:
    models = await ModelRegistryRepository(session).list(project_id=project_id, stage=stage)
    return [ModelResponse.model_validate(m) for m in models]


@router.post("/models/{model_id}/promote", response_model=ModelResponse,
             dependencies=[require_role(Role.ENGINEER)])
async def promote_model(
    model_id: UUID, session: DbSession, actor: CurrentUser
) -> ModelResponse:
    """Promote to production — enforces the human-approval gate for high-risk models."""
    repo = ModelRegistryRepository(session)
    model = await repo.get(model_id)
    risk = RiskLevel(model.risk_level)
    approval = ApprovalStatus(model.approval_status)
    if risk == RiskLevel.PROHIBITED:
        raise BusinessRuleViolation("Prohibited-risk models can never be deployed")
    if risk == RiskLevel.HIGH and approval != ApprovalStatus.APPROVED:
        raise ApprovalRequiredError(
            "High-risk models require an approved review before production deployment"
        )
    # Keep the previous production version for one-click rollback.
    current = await repo.list(project_id=model.project_id, name=model.name,
                              stage=ModelStage.PRODUCTION.value)
    for previous in current:
        previous.stage = ModelStage.ARCHIVED.value
        model.rollback_version = previous.version
    model.stage = ModelStage.PRODUCTION.value
    await AuditRepository(session).append(
        actor_id=actor.id, action="model.promoted", resource_type="model",
        resource_id=str(model_id), details={"version": model.version},
    )
    return ModelResponse.model_validate(model)


@router.post("/models/{model_id}/rollback", response_model=ModelResponse,
             dependencies=[require_role(Role.ENGINEER)])
async def rollback_model(
    model_id: UUID, session: DbSession, actor: CurrentUser
) -> ModelResponse:
    repo = ModelRegistryRepository(session)
    model = await repo.get(model_id)
    if not model.rollback_version:
        raise BusinessRuleViolation("No previous version available for rollback")
    candidates = await repo.list(project_id=model.project_id, name=model.name,
                                 version=model.rollback_version)
    if not candidates:
        raise BusinessRuleViolation("Rollback target version no longer exists")
    model.stage = ModelStage.ARCHIVED.value
    candidates[0].stage = ModelStage.PRODUCTION.value
    await AuditRepository(session).append(
        actor_id=actor.id, action="model.rolled_back", resource_type="model",
        resource_id=str(model_id), details={"to_version": model.rollback_version},
    )
    return ModelResponse.model_validate(candidates[0])


@router.get("/models/{model_id}/card", dependencies=[require_role(Role.VIEWER)])
async def model_card(model_id: UUID, session: DbSession) -> dict:
    """Model card (F-51) generated live from registry metadata — never stale."""
    model = await ModelRegistryRepository(session).get(model_id)
    return {
        "model_card": {
            "name": model.name,
            "version": model.version,
            "type": model.model_type,
            "stage": model.stage,
            "risk_level": model.risk_level,
            "approval_status": model.approval_status,
            "owner_id": str(model.owner_id) if model.owner_id else None,
            "training_dataset": model.training_dataset,
            "evaluation_metrics": model.metrics,
            "artifact_uri": model.artifact_uri,
            "created_at": model.created_at.isoformat(),
            "intended_use": "See project documentation",
            "limitations": "Model outputs require human review for high-stakes decisions",
        }
    }


# -------------------------------------------------------------------- approvals
@router.post("/approvals", response_model=ApprovalResponse, status_code=201,
             dependencies=[require_role(Role.ENGINEER)])
async def request_approval(
    body: ApprovalRequestCreate, session: DbSession, actor: CurrentUser
) -> ApprovalResponse:
    approval = await ApprovalRepository(session).add(
        ApprovalModel(
            resource_type=body.resource_type, resource_id=body.resource_id,
            requested_by=actor.id, justification=body.justification,
        )
    )
    await AuditRepository(session).append(
        actor_id=actor.id, action="approval.requested", resource_type=body.resource_type,
        resource_id=body.resource_id,
    )
    return ApprovalResponse.model_validate(approval)


@router.get("/approvals", response_model=list[ApprovalResponse],
            dependencies=[require_role(Role.COMPLIANCE_OFFICER)])
async def list_approvals(
    session: DbSession, status: str | None = None
) -> list[ApprovalResponse]:
    items = await ApprovalRepository(session).list(status=status)
    return [ApprovalResponse.model_validate(a) for a in items]


@router.post("/approvals/{approval_id}/decide", response_model=ApprovalResponse,
             dependencies=[require_role(Role.COMPLIANCE_OFFICER)])
async def decide_approval(
    approval_id: UUID, body: ApprovalDecision, session: DbSession, actor: CurrentUser
) -> ApprovalResponse:
    """Human-in-the-loop decision (F-53). Reviewer must differ from requester."""
    repo = ApprovalRepository(session)
    approval = await repo.get(approval_id)
    if approval.requested_by == actor.id:
        raise BusinessRuleViolation("Requesters cannot review their own approval requests")
    approval.status = (
        ApprovalStatus.APPROVED.value if body.approve else ApprovalStatus.REJECTED.value
    )
    approval.reviewed_by = actor.id
    approval.review_comment = body.comment[:2000]
    # Propagate the decision to the governed resource when it is a model.
    if approval.resource_type == "model":
        model = await ModelRegistryRepository(session).find(UUID(approval.resource_id))
        if model is not None:
            model.approval_status = approval.status
    await AuditRepository(session).append(
        actor_id=actor.id,
        action="approval.approved" if body.approve else "approval.rejected",
        resource_type=approval.resource_type, resource_id=approval.resource_id,
    )
    return ApprovalResponse.model_validate(approval)


# ---------------------------------------------------------------------- audit
@router.get("/audit", response_model=list[AuditEventResponse],
            dependencies=[require_role(Role.COMPLIANCE_OFFICER)])
async def audit_trail(
    session: DbSession,
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
    resource_type: str | None = None,
) -> list[AuditEventResponse]:
    events = await AuditRepository(session).list(
        limit=min(limit, 500), offset=offset, action=action, resource_type=resource_type
    )
    return [AuditEventResponse.model_validate(e) for e in events]


# ------------------------------------------------------------------ inventory
@router.get("/inventory", dependencies=[require_role(Role.VIEWER)])
async def ai_inventory(session: DbSession) -> dict:
    """AI inventory (F-50): everything AI-related running on the platform."""
    models = await ModelRegistryRepository(session).count()
    prompts = await PromptRepository(session).count()
    knowledge_bases = await KnowledgeBaseRepository(session).count()
    pending = await ApprovalRepository(session).count(status="pending_review")
    return {
        "models": models,
        "prompts": prompts,
        "knowledge_bases": knowledge_bases,
        "pending_approvals": pending,
        "generated_at": datetime.now(UTC).isoformat(),
        "next_review_due": (datetime.now(UTC) + timedelta(days=90)).date().isoformat(),
    }
