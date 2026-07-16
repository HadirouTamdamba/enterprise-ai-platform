"""Integration tests for the LLM gateway: routing, fallback, accounting."""

import pytest

from app.ai.gateway.service import LLMGatewayService
from app.core.exceptions import ProviderUnavailableError
from app.domain.ports.llm import ChatMessage, ChatRequest, MessageRole
from app.infrastructure.llm.providers import FakeProvider
from app.infrastructure.llm.registry import ProviderRegistry


class BrokenProvider(FakeProvider):
    name = "broken"

    def available(self) -> bool:
        return True

    async def chat(self, request):
        raise ProviderUnavailableError("simulated outage")


def _request() -> ChatRequest:
    return ChatRequest(
        messages=[ChatMessage(role=MessageRole.USER, content="hello world")],
        model="fake-model",
    )


@pytest.fixture
def registry() -> ProviderRegistry:
    fake = FakeProvider("fallback answer")
    reg = ProviderRegistry({"broken": BrokenProvider(), "fake": fake})
    return reg


async def test_gateway_returns_response_with_usage(registry):
    gateway = LLMGatewayService(registry)
    route = gateway.resolve(provider="fake", model="fake-model")
    response = await gateway.chat(_request(), route)
    assert response.content
    assert response.usage.total_tokens > 0
    assert response.provider == "fake"


async def test_gateway_falls_back_when_primary_fails(registry, monkeypatch):
    gateway = LLMGatewayService(registry)
    # Primary broken, fallback fake — resolve manually to control the chain.
    from app.domain.services.routing import ModelTarget, RoutingDecision

    route = RoutingDecision(
        primary=ModelTarget("broken", "fake-model"),
        fallbacks=(ModelTarget("fake", "fake-model"),),
    )
    response = await gateway.chat(_request(), route)
    assert response.provider == "fake"
    assert response.content == "fallback answer"


async def test_gateway_raises_when_all_providers_fail():
    registry = ProviderRegistry({"broken": BrokenProvider()})
    gateway = LLMGatewayService(registry)
    from app.domain.services.routing import ModelTarget, RoutingDecision

    route = RoutingDecision(primary=ModelTarget("broken", "fake-model"))
    with pytest.raises(ProviderUnavailableError):
        await gateway.chat(_request(), route)


async def test_deterministic_requests_are_cached(registry):
    gateway = LLMGatewayService(registry)
    route = gateway.resolve(provider="fake", model="fake-model")
    request = _request()
    request.temperature = 0.0
    first = await gateway.chat(request, route)
    second = await gateway.chat(request, route)
    assert not first.cached
    assert second.cached
