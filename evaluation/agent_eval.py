"""Agent evaluation (F-34): task success, tool success and cost per task,
measured against the deterministic Fake provider (offline) or a real provider
when keys are configured."""

import asyncio
import json
import os
import sys

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "evaluation-only-secret-0123456789")
os.environ.setdefault("DEFAULT_LLM_PROVIDER", "fake")
os.environ.setdefault("DEFAULT_LLM_MODEL", "fake-model")
os.environ.setdefault("FALLBACK_LLM_PROVIDER", "fake")
os.environ.setdefault("FALLBACK_LLM_MODEL", "fake-model")

from app.ai.agents.catalog import build_agent, list_agents  # noqa: E402
from app.ai.agents.orchestrator import AgentOrchestrator, AgentTool  # noqa: E402
from app.ai.gateway.service import LLMGatewayService  # noqa: E402
from app.infrastructure.llm.registry import get_provider_registry  # noqa: E402

TASKS = [
    ("planner", "Plan the rollout of a governed RAG assistant for a bank's risk team"),
    ("critic", "Critique this statement: our chatbot never hallucinates"),
    ("reporting", "Summarize: 3 incidents this week, all resolved, MTTR 42 minutes"),
]


async def evaluate() -> dict:
    gateway = LLMGatewayService(get_provider_registry())
    orchestrator = AgentOrchestrator(gateway)

    tool_calls = {"count": 0}

    async def echo_tool(arguments: dict) -> str:
        tool_calls["count"] += 1
        return f"echo: {json.dumps(arguments)}"

    tool = AgentTool(
        name="echo",
        description="Echo the input back (evaluation tool).",
        parameters={"type": "object", "properties": {"input": {"type": "string"}}},
        handler=echo_tool,
    )

    successes = 0
    total_cost = 0.0
    for agent_name, task in TASKS:
        spec = build_agent(agent_name, [tool])
        result = await orchestrator.run(spec, task, max_iterations=3, max_cost_usd=0.5)
        if result.output and not result.output.startswith("Stopped:"):
            successes += 1
        total_cost += result.cost_usd

    report = {
        "agents_available": len(list_agents()),
        "tasks": len(TASKS),
        "task_success_rate": round(successes / len(TASKS), 3),
        "total_cost_usd": round(total_cost, 6),
        "avg_cost_per_task_usd": round(total_cost / len(TASKS), 6),
    }
    report["passed"] = report["task_success_rate"] >= 0.66 and report["agents_available"] == 10
    return report


if __name__ == "__main__":
    result = asyncio.run(evaluate())
    print(json.dumps(result, indent=2))  # noqa: T201 — CLI entrypoint
    sys.exit(0 if result["passed"] else 1)
