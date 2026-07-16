"""LLM Gateway endpoints (F-10..F-13): unified chat across all providers."""

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession, enforce_rate_limit, require_role
from app.api.v1.schemas import ChatCompletionRequest, ChatCompletionResponse, UsageResponse
from app.ai.gateway.pricing import get_pricing
from app.ai.gateway.service import LLMGatewayService
from app.ai.guardrails.pipeline import validate_input
from app.domain.entities.identity import Role
from app.domain.ports.llm import ChatMessage, ChatRequest, MessageRole
from app.domain.services.routing import estimate_cost_usd
from app.infrastructure.database.repositories.ai import UsageRepository
from app.infrastructure.database.repositories.identity import ProjectRepository
from app.infrastructure.llm.registry import get_provider_registry

router = APIRouter(prefix="/gateway", tags=["llm-gateway"],
                   dependencies=[Depends(enforce_rate_limit)])


@router.get("/providers", dependencies=[require_role(Role.VIEWER)])
async def list_providers() -> dict:
    """Providers configured on this deployment (never exposes keys)."""
    return {"configured": get_provider_registry().configured()}


@router.post("/chat", response_model=ChatCompletionResponse,
             dependencies=[require_role(Role.ANALYST)])
async def chat_completion(
    body: ChatCompletionRequest, session: DbSession, user: CurrentUser
) -> ChatCompletionResponse | StreamingResponse:
    for message in body.messages:
        if message.role == "user":
            validate_input(message.content)

    project = None
    if body.project_id:
        project = await ProjectRepository(session).get(body.project_id)

    gateway = LLMGatewayService(get_provider_registry(), UsageRepository(session))
    route = gateway.resolve(
        provider=body.provider,
        model=body.model,
        project_provider=project.default_llm_provider if project else None,
        project_model=project.default_llm_model if project else None,
    )
    request = ChatRequest(
        messages=[ChatMessage(role=MessageRole(m.role), content=m.content) for m in body.messages],
        model=route.primary.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        response_schema=body.response_schema,
    )

    if body.stream:
        async def event_stream():
            async for chunk in gateway.chat_stream(request, route):
                yield f"data: {json.dumps({'delta': chunk.delta, 'finish_reason': chunk.finish_reason})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    response = await gateway.chat(
        request, route, user_id=user.id, project_id=body.project_id, feature="gateway"
    )
    cost = estimate_cost_usd(
        response.usage.prompt_tokens, response.usage.completion_tokens,
        get_pricing(), response.model,
    )
    return ChatCompletionResponse(
        content=response.content,
        provider=response.provider,
        model=response.model,
        finish_reason=response.finish_reason,
        usage=UsageResponse(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            cost_usd=cost,
            latency_ms=round(response.latency_ms, 2),
            cached=response.cached,
        ),
    )
