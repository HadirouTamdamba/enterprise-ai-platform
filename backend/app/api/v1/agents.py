"""Agent endpoints (F-30..F-34): catalog listing and guarded execution."""

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, enforce_rate_limit, require_role
from app.api.v1.schemas import AgentRunRequest, AgentRunResponse, AgentStepResponse, UsageResponse
from app.ai.agents.catalog import build_agent, list_agents
from app.ai.agents.orchestrator import AgentOrchestrator, AgentTool
from app.ai.gateway.service import LLMGatewayService
from app.ai.rag.service import RAGService
from app.core.exceptions import NotFoundError
from app.domain.entities.identity import Role
from app.infrastructure.database.repositories.ai import (
    AuditRepository,
    KnowledgeBaseRepository,
    UsageRepository,
)
from app.infrastructure.llm.registry import get_provider_registry
from app.infrastructure.vector.qdrant_store import get_vector_store

router = APIRouter(prefix="/agents", tags=["agents"],
                   dependencies=[Depends(enforce_rate_limit)])


@router.get("", dependencies=[require_role(Role.VIEWER)])
async def get_agents() -> list[dict]:
    return list_agents()


@router.post("/run", response_model=AgentRunResponse,
             dependencies=[require_role(Role.ANALYST)])
async def run_agent(
    body: AgentRunRequest, session: DbSession, user: CurrentUser
) -> AgentRunResponse:
    gateway = LLMGatewayService(get_provider_registry(), UsageRepository(session))

    tools: list[AgentTool] = []
    if body.knowledge_base_id:
        kb = await KnowledgeBaseRepository(session).get(body.knowledge_base_id)
        rag = RAGService(get_vector_store(), gateway)

        async def search_knowledge(arguments: dict) -> str:
            query = str(arguments.get("query", ""))
            hits = await rag.retrieve(kb, query, top_k=6)
            if not hits:
                return "No relevant passages found."
            return "\n\n".join(
                f"[{h.payload.get('filename')} p.{h.payload.get('page')}] "
                f"{h.payload.get('content')}"
                for h in hits
            )

        tools.append(
            AgentTool(
                name="search_knowledge",
                description="Search the project knowledge base for relevant passages.",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                handler=search_knowledge,
            )
        )

    try:
        spec = build_agent(body.agent, tools)
    except KeyError as exc:
        raise NotFoundError(str(exc)) from exc

    orchestrator = AgentOrchestrator(gateway)
    result = await orchestrator.run(
        spec, body.task,
        user_id=user.id, project_id=body.project_id,
        max_iterations=body.max_iterations, max_cost_usd=body.max_cost_usd,
    )
    await AuditRepository(session).append(
        actor_id=user.id, action="agent.run", resource_type="agent", resource_id=body.agent,
        details={"iterations": len(result.steps), "cost_usd": result.cost_usd},
    )
    return AgentRunResponse(
        agent=result.agent,
        output=result.output,
        steps=[
            AgentStepResponse(iteration=s.iteration, thought=s.thought,
                              action=s.action, result=s.result)
            for s in result.steps
        ],
        usage=UsageResponse(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.prompt_tokens + result.completion_tokens,
            cost_usd=round(result.cost_usd, 6),
            latency_ms=round(result.latency_ms, 2),
        ),
    )
