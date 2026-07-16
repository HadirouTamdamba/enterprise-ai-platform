"""Agent orchestrator (F-30..F-34): plan → act → reflect with hard budget guards.

Agents are declarative specs (role, system prompt, tools, limits). Tools are typed,
validated, and every execution is logged. The loop stops on final answer, max
iterations, or cost ceiling — whichever comes first.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from uuid import UUID

from app.ai.gateway.service import LLMGatewayService
from app.ai.guardrails.pipeline import validate_input
from app.core.logging import get_logger
from app.domain.ports.llm import ChatMessage, ChatRequest, MessageRole
from app.domain.services.routing import estimate_cost_usd
from app.infrastructure.observability.metrics import AGENT_RUNS

logger = get_logger(__name__)

ToolFn = Callable[[dict], Awaitable[str]]


@dataclass(slots=True)
class AgentTool:
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: ToolFn


@dataclass(slots=True)
class AgentSpec:
    name: str
    role: str
    system_prompt: str
    tools: list[AgentTool] = field(default_factory=list)
    reflection: bool = True
    max_iterations: int = 6
    max_cost_usd: float = 1.0


@dataclass(slots=True)
class AgentStep:
    iteration: int
    thought: str
    action: str
    result: str


@dataclass(slots=True)
class AgentResult:
    agent: str
    output: str
    steps: list[AgentStep]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


_AGENT_PROTOCOL = """You work in strict JSON steps. At each step reply with ONE JSON object:
{"thought": "<your reasoning>", "action": "tool_name" | "final", "input": {...} | "<final answer>"}

Available tools:
{tools}

Rules:
- Use "final" with your complete answer in "input" when the task is done.
- Never invent tool names. Validate your JSON. Emit exactly ONE JSON object per step.
- Never repeat a tool call you already made with the same or similar input.
- Be efficient: every step costs money — finish as soon as the task is solved."""


class AgentOrchestrator:
    def __init__(self, gateway: LLMGatewayService) -> None:
        self._gateway = gateway

    async def run(
        self,
        spec: AgentSpec,
        task: str,
        *,
        user_id: UUID | None = None,
        project_id: UUID | None = None,
        max_iterations: int | None = None,
        max_cost_usd: float | None = None,
    ) -> AgentResult:
        validate_input(task)  # guardrails on the task itself
        iterations = min(max_iterations or spec.max_iterations, 20)
        budget = min(max_cost_usd or spec.max_cost_usd, 50.0)

        tool_index = {tool.name: tool for tool in spec.tools}
        tools_doc = "\n".join(
            f"- {t.name}: {t.description} — parameters: {json.dumps(t.parameters)}"
            for t in spec.tools
        ) or "- (no tools; reason and answer directly)"

        messages: list[ChatMessage] = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=spec.system_prompt
                + "\n\n"
                + _AGENT_PROTOCOL.replace("{tools}", tools_doc),
            ),
            ChatMessage(role=MessageRole.USER, content=f"Task: {task}"),
        ]

        steps: list[AgentStep] = []
        result = AgentResult(agent=spec.name, output="", steps=steps)
        route = self._gateway.resolve(provider=None, model=None)

        for iteration in range(1, iterations + 1):
            request = ChatRequest(messages=list(messages), model="", temperature=0.1)
            response = await self._gateway.chat(
                request, route, user_id=user_id, project_id=project_id, feature="agent"
            )
            result.prompt_tokens += response.usage.prompt_tokens
            result.completion_tokens += response.usage.completion_tokens
            result.latency_ms += response.latency_ms
            result.cost_usd += estimate_cost_usd(
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                self._gateway._pricing,
                response.model,
            )

            step_data = _parse_step(response.content)
            thought = step_data.get("thought", "")
            action = step_data.get("action", "final")

            if action == "final" or (action not in tool_index and action != "final"):
                if action != "final" and action not in tool_index:
                    # Unknown tool → treat model output as the final answer, flagged.
                    logger.warning("agent_unknown_tool", agent=spec.name, action=action)
                output = step_data.get("input", response.content)
                result.output = (
                    output
                    if isinstance(output, str)
                    else json.dumps(output, indent=2, ensure_ascii=False)
                )
                steps.append(AgentStep(iteration, thought, "final", result.output[:500]))
                break

            tool = tool_index[action]
            tool_input = step_data.get("input", {})
            try:
                tool_result = await tool.handler(
                    tool_input if isinstance(tool_input, dict) else {"input": tool_input}
                )
            except Exception as exc:  # tools may fail; the agent must recover
                tool_result = f"TOOL ERROR: {type(exc).__name__}: {exc}"
            logger.info("agent_tool_executed", agent=spec.name, tool=action)
            steps.append(AgentStep(iteration, thought, action, tool_result[:500]))

            messages.append(ChatMessage(role=MessageRole.ASSISTANT, content=response.content))
            messages.append(
                ChatMessage(role=MessageRole.USER, content=f"Tool result: {tool_result[:4000]}")
            )

            if result.cost_usd >= budget:
                result.output = (
                    "Stopped: cost budget reached before completion. Partial progress:\n"
                    + "\n".join(f"{s.action}: {s.result[:200]}" for s in steps)
                )
                break
        else:
            # Iterations exhausted without a final answer — force one synthesis turn
            # so the caller always receives a usable conclusion.
            messages.append(
                ChatMessage(
                    role=MessageRole.USER,
                    content="You have used all your steps. Based on everything gathered "
                    "above, give your final answer now as plain text (no JSON, no tools). "
                    "Answer in the language of the original task.",
                )
            )
            response = await self._gateway.chat(
                ChatRequest(messages=list(messages), model="", temperature=0.1),
                route, user_id=user_id, project_id=project_id, feature="agent",
            )
            result.prompt_tokens += response.usage.prompt_tokens
            result.completion_tokens += response.usage.completion_tokens
            result.output = response.content.strip() or "Stopped: maximum iterations reached."
            steps.append(AgentStep(iterations + 1, "", "forced_final", result.output[:500]))

        if spec.reflection and result.output and not result.output.startswith("Stopped:"):
            result = await self._reflect(spec, task, result, route, user_id, project_id)

        AGENT_RUNS.labels(spec.name, "success" if result.output else "failure").inc()
        return result

    async def _reflect(
        self,
        spec: AgentSpec,
        task: str,
        result: AgentResult,
        route,
        user_id: UUID | None,
        project_id: UUID | None,
    ) -> AgentResult:
        """One critique-and-improve pass over the draft answer."""
        request = ChatRequest(
            messages=[
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content="You are a strict reviewer. Improve the draft answer for accuracy, "
                    "completeness and clarity. Return only the improved answer.",
                ),
                ChatMessage(
                    role=MessageRole.USER,
                    content=f"Task: {task}\n\nDraft answer:\n{result.output}",
                ),
            ],
            model="",
            temperature=0.1,
        )
        response = await self._gateway.chat(
            request, route, user_id=user_id, project_id=project_id, feature="agent"
        )
        result.prompt_tokens += response.usage.prompt_tokens
        result.completion_tokens += response.usage.completion_tokens
        if response.content.strip():
            result.output = response.content.strip()
        return result


def _parse_step(content: str) -> dict:
    """Extract the first valid JSON step object.

    Tolerates markdown fences, surrounding prose, and models that emit several
    JSON objects in one turn (only the first actionable one counts).
    """
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            candidate, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            candidate = None
        if isinstance(candidate, dict) and "action" in candidate:
            return candidate
        start = text.find("{", start + 1)
    return {"thought": "", "action": "final", "input": content}
