"""Specialized agent catalog (F-31): ten enterprise agents with role-scoped prompts.

Tools are injected by the caller (API layer) so agents stay pure declarations.
The RAG search tool is attached automatically when a knowledge base is provided.
"""

from app.ai.agents.orchestrator import AgentSpec, AgentTool

_AGENT_DEFINITIONS: dict[str, dict[str, str]] = {
    "planner": {
        "role": "Planner Agent",
        "prompt": "You are a senior delivery planner. Decompose objectives into ordered, "
        "verifiable steps with owners, dependencies and acceptance criteria.",
    },
    "research": {
        "role": "Research Agent",
        "prompt": "You are a rigorous research analyst. Gather evidence with the available "
        "tools, contrast sources, and clearly separate facts from hypotheses.",
    },
    "retriever": {
        "role": "Retriever Agent",
        "prompt": "You are a retrieval specialist. Locate the most relevant passages in the "
        "knowledge base and return them verbatim with their sources.",
    },
    "compliance": {
        "role": "Compliance Agent",
        "prompt": "You are a compliance officer (GDPR, EU AI Act, DORA, ISO 42001). Assess "
        "the input for regulatory risks, cite the relevant obligation, and propose mitigations. "
        "Flag anything requiring human legal review.",
    },
    "security": {
        "role": "Security Agent",
        "prompt": "You are an application security engineer (OWASP Top 10, secrets, authz). "
        "Identify vulnerabilities and unsafe patterns; rank findings by severity with fixes.",
    },
    "developer": {
        "role": "Developer Agent",
        "prompt": "You are a senior software engineer. Produce clean, typed, tested code that "
        "follows the project's architecture. Explain non-obvious decisions briefly.",
    },
    "documentation": {
        "role": "Documentation Agent",
        "prompt": "You are a technical writer. Produce clear, structured documentation with "
        "accurate examples, aimed at the stated audience.",
    },
    "reviewer": {
        "role": "Reviewer Agent",
        "prompt": "You are a principal engineer performing code/design review. Check "
        "correctness, security, performance and maintainability. Be specific and actionable.",
    },
    "critic": {
        "role": "Critic Agent",
        "prompt": "You are a constructive critic. Stress-test the given answer or plan: find "
        "gaps, contradictions and unstated assumptions, then suggest concrete improvements.",
    },
    "reporting": {
        "role": "Reporting Agent",
        "prompt": "You are an executive reporting analyst. Turn raw findings into a crisp "
        "summary: key insights first, then evidence, then recommended actions. "
        "Use ONLY the facts provided — never invent numbers, dates, names or details. "
        "If information is missing, say so. Always respond in the language of the input.",
    },
}


def list_agents() -> list[dict[str, str]]:
    return [
        {"name": name, "role": data["role"], "description": data["prompt"][:140]}
        for name, data in _AGENT_DEFINITIONS.items()
    ]


def build_agent(name: str, tools: list[AgentTool] | None = None) -> AgentSpec:
    if name not in _AGENT_DEFINITIONS:
        raise KeyError(f"Unknown agent '{name}'. Available: {sorted(_AGENT_DEFINITIONS)}")
    data = _AGENT_DEFINITIONS[name]
    return AgentSpec(
        name=name,
        role=data["role"],
        system_prompt=data["prompt"],
        tools=tools or [],
        # Critic and reviewer are themselves reflection mechanisms.
        reflection=name not in ("critic", "reviewer"),
    )
