"""LLM Gateway — the single entry point for every model call on the platform.

Responsibilities: routing (with project defaults), fallback chains, retries,
response caching, token/cost accounting, metrics. Guardrails are applied by
callers (RAG/agents/API) before and after gateway calls.
"""

import hashlib
import json
from collections.abc import AsyncIterator
from dataclasses import asdict
from uuid import UUID

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.ai.gateway.pricing import get_pricing
from app.core.config import get_settings
from app.core.exceptions import ModelInferenceError, ProviderUnavailableError
from app.core.logging import get_logger
from app.domain.ports.llm import ChatRequest, ChatResponse, StreamChunk
from app.domain.services.routing import RoutingDecision, estimate_cost_usd, resolve_route
from app.infrastructure.database.models import UsageRecordModel
from app.infrastructure.database.repositories.ai import UsageRepository
from app.infrastructure.llm.registry import ProviderRegistry
from app.infrastructure.observability.metrics import (
    LLM_CACHE_HITS,
    LLM_COST,
    LLM_LATENCY,
    LLM_REQUESTS,
    LLM_TOKENS,
)

logger = get_logger(__name__)


class ResponseCache:
    """Exact-match response cache (Redis in prod, dict fallback in tests)."""

    def __init__(self, redis=None, ttl_seconds: int = 3600) -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        self._memory: dict[str, str] = {}

    @staticmethod
    def key(request: ChatRequest) -> str:
        digest = hashlib.sha256(
            json.dumps(
                {
                    "model": request.model,
                    "messages": [asdict(m) for m in request.messages],
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                },
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest()
        return f"gw:cache:{digest}"

    async def get(self, key: str) -> dict | None:
        try:
            raw = await self._redis.get(key) if self._redis else self._memory.get(key)
        except Exception:
            return None
        return json.loads(raw) if raw else None

    async def set(self, key: str, response: ChatResponse) -> None:
        payload = json.dumps(
            {
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "finish_reason": response.finish_reason,
            }
        )
        try:
            if self._redis:
                await self._redis.set(key, payload, ex=self._ttl)
            else:
                self._memory[key] = payload
        except Exception:  # cache failures must never break inference
            logger.warning("gateway_cache_write_failed")


class LLMGatewayService:
    def __init__(
        self,
        registry: ProviderRegistry,
        usage_repo: UsageRepository | None = None,
        cache: ResponseCache | None = None,
    ) -> None:
        self._registry = registry
        self._usage_repo = usage_repo
        self._cache = cache or ResponseCache()
        self._pricing = get_pricing()

    def resolve(
        self,
        *,
        provider: str | None,
        model: str | None,
        project_provider: str | None = None,
        project_model: str | None = None,
    ) -> RoutingDecision:
        s = get_settings()
        return resolve_route(
            requested_provider=provider,
            requested_model=model,
            project_provider=project_provider,
            project_model=project_model,
            default_provider=s.default_llm_provider,
            default_model=s.default_llm_model,
            fallback_provider=s.fallback_llm_provider,
            fallback_model=s.fallback_llm_model,
        )

    @retry(
        retry=retry_if_exception_type(ProviderUnavailableError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=8),
        reraise=True,
    )
    async def _call_provider(self, provider_name: str, request: ChatRequest) -> ChatResponse:
        provider = self._registry.get(provider_name)
        return await provider.chat(request)

    async def chat(
        self,
        request: ChatRequest,
        route: RoutingDecision,
        *,
        user_id: UUID | None = None,
        project_id: UUID | None = None,
        feature: str = "gateway",
        use_cache: bool = True,
    ) -> ChatResponse:
        cache_key = ResponseCache.key(request)
        if use_cache and request.temperature == 0.0:
            cached = await self._cache.get(cache_key)
            if cached:
                LLM_CACHE_HITS.labels(cached["provider"], cached["model"]).inc()
                response = ChatResponse(
                    content=cached["content"],
                    model=cached["model"],
                    provider=cached["provider"],
                    finish_reason=cached["finish_reason"],
                    cached=True,
                )
                await self._record(response, user_id, project_id, feature, cost_usd=0.0)
                return response

        last_error: Exception | None = None
        for target in route.chain:
            request.model = target.model
            try:
                response = await self._call_provider(target.provider, request)
            except (ProviderUnavailableError, ModelInferenceError) as exc:
                LLM_REQUESTS.labels(target.provider, target.model, "error").inc()
                logger.warning(
                    "gateway_provider_failed", provider=target.provider, model=target.model
                )
                last_error = exc
                continue

            cost = estimate_cost_usd(
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                self._pricing,
                response.model,
            )
            LLM_REQUESTS.labels(response.provider, response.model, "success").inc()
            LLM_TOKENS.labels(response.provider, response.model, "input").inc(
                response.usage.prompt_tokens
            )
            LLM_TOKENS.labels(response.provider, response.model, "output").inc(
                response.usage.completion_tokens
            )
            LLM_COST.labels(response.provider, response.model).inc(cost)
            LLM_LATENCY.labels(response.provider, response.model).observe(
                response.latency_ms / 1000
            )
            if use_cache and request.temperature == 0.0:
                await self._cache.set(cache_key, response)
            await self._record(response, user_id, project_id, feature, cost_usd=cost)
            return response

        raise last_error or ProviderUnavailableError("No provider in the routing chain succeeded")

    async def chat_stream(
        self, request: ChatRequest, route: RoutingDecision
    ) -> AsyncIterator[StreamChunk]:
        target = route.primary
        request.model = target.model
        provider = self._registry.get(target.provider)
        async for chunk in provider.chat_stream(request):
            yield chunk

    async def _record(
        self,
        response: ChatResponse,
        user_id: UUID | None,
        project_id: UUID | None,
        feature: str,
        *,
        cost_usd: float,
    ) -> None:
        if self._usage_repo is None:
            return
        await self._usage_repo.add(
            UsageRecordModel(
                provider=response.provider,
                model=response.model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                cost_usd=cost_usd,
                latency_ms=response.latency_ms,
                user_id=user_id,
                project_id=project_id,
                feature=feature,
                cached=response.cached,
                success=True,
            )
        )
