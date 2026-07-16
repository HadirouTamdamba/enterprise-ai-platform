"""Unit tests for pure domain logic — no I/O."""

from uuid import uuid4

import pytest

from app.domain.entities.ai import (
    ApprovalStatus,
    ModelStage,
    PromptVersion,
    RegisteredModel,
    RiskLevel,
)
from app.domain.entities.identity import Role, role_at_least
from app.domain.services.routing import estimate_cost_usd, resolve_route


class TestRoleHierarchy:
    def test_admin_outranks_everyone(self):
        for role in Role:
            assert role_at_least(Role.PLATFORM_ADMIN, role)

    def test_viewer_only_matches_viewer(self):
        assert role_at_least(Role.VIEWER, Role.VIEWER)
        assert not role_at_least(Role.VIEWER, Role.ENGINEER)

    def test_compliance_officer_is_not_workspace_admin(self):
        assert not role_at_least(Role.COMPLIANCE_OFFICER, Role.WORKSPACE_ADMIN)


class TestRouting:
    def test_explicit_request_wins(self):
        decision = resolve_route(
            requested_provider="mistral", requested_model="mistral-large-latest",
            project_provider="openai", project_model="gpt-4o",
            default_provider="anthropic", default_model="claude-sonnet-5",
            fallback_provider="openai", fallback_model="gpt-4o",
        )
        assert decision.primary.provider == "mistral"
        assert decision.fallbacks[0].provider == "openai"

    def test_project_default_beats_platform_default(self):
        decision = resolve_route(
            requested_provider=None, requested_model=None,
            project_provider="gemini", project_model="gemini-2.0-flash",
            default_provider="anthropic", default_model="claude-sonnet-5",
            fallback_provider="openai", fallback_model="gpt-4o",
        )
        assert decision.primary.provider == "gemini"

    def test_no_duplicate_fallback(self):
        decision = resolve_route(
            requested_provider="openai", requested_model="gpt-4o",
            project_provider=None, project_model=None,
            default_provider="anthropic", default_model="claude-sonnet-5",
            fallback_provider="openai", fallback_model="gpt-4o",
        )
        assert decision.fallbacks == ()

    def test_cost_estimation(self):
        pricing = {"m": (3.0, 15.0)}
        assert estimate_cost_usd(1_000_000, 0, pricing, "m") == 3.0
        assert estimate_cost_usd(0, 1_000_000, pricing, "m") == 15.0
        assert estimate_cost_usd(100, 100, pricing, "unknown-model") == 0.0


class TestPromptVersion:
    def test_render_substitutes_variables(self):
        version = PromptVersion(
            prompt_id=uuid4(), version=1,
            template="Hello {{name}}, question: {{question}}",
            variables=["name", "question"],
        )
        result = version.render({"name": "Ada", "question": "why?"})
        assert result == "Hello Ada, question: why?"

    def test_render_missing_variable_raises(self):
        version = PromptVersion(
            prompt_id=uuid4(), version=1, template="{{a}}", variables=["a"]
        )
        with pytest.raises(ValueError, match="Missing prompt variables"):
            version.render({})


class TestModelGovernanceRules:
    def _model(self, risk: RiskLevel, approval: ApprovalStatus) -> RegisteredModel:
        return RegisteredModel(
            name="m", version="1", project_id=uuid4(), model_type="classifier",
            stage=ModelStage.STAGING, approval_status=approval, risk_level=risk,
        )

    def test_prohibited_never_deployable(self):
        model = self._model(RiskLevel.PROHIBITED, ApprovalStatus.APPROVED)
        assert not model.can_deploy_to_production()

    def test_high_risk_requires_approval(self):
        assert not self._model(
            RiskLevel.HIGH, ApprovalStatus.PENDING_REVIEW
        ).can_deploy_to_production()
        assert self._model(RiskLevel.HIGH, ApprovalStatus.APPROVED).can_deploy_to_production()
