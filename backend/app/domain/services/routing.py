"""Model routing policy — pure business rules, no I/O.

Resolution order: explicit request → project defaults → platform defaults,
then a fallback chain for resilience when a provider fails.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelTarget:
    provider: str
    model: str


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    primary: ModelTarget
    fallbacks: tuple[ModelTarget, ...] = ()

    @property
    def chain(self) -> tuple[ModelTarget, ...]:
        return (self.primary, *self.fallbacks)


def resolve_route(
    *,
    requested_provider: str | None,
    requested_model: str | None,
    project_provider: str | None,
    project_model: str | None,
    default_provider: str,
    default_model: str,
    fallback_provider: str,
    fallback_model: str,
) -> RoutingDecision:
    """Pick provider/model with deterministic precedence and build the fallback chain."""
    if requested_provider and requested_model:
        primary = ModelTarget(requested_provider, requested_model)
    elif project_provider and project_model:
        primary = ModelTarget(project_provider, project_model)
    else:
        primary = ModelTarget(default_provider, default_model)

    fallback = ModelTarget(fallback_provider, fallback_model)
    fallbacks = () if fallback == primary else (fallback,)
    return RoutingDecision(primary=primary, fallbacks=fallbacks)


def estimate_cost_usd(
    prompt_tokens: int,
    completion_tokens: int,
    pricing: dict[str, tuple[float, float]],
    model: str,
) -> float:
    """Cost from a configurable pricing table: model -> (usd_per_1m_in, usd_per_1m_out)."""
    rate_in, rate_out = pricing.get(model, (0.0, 0.0))
    return round(prompt_tokens * rate_in / 1e6 + completion_tokens * rate_out / 1e6, 8)
