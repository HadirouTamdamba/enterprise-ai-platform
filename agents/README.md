# Agent Definitions

Declarative definitions of the platform's specialized agents. The runtime catalog lives in
`backend/app/ai/agents/catalog.py`; this directory documents each agent's contract for
governance review (role, inputs, outputs, tools, memory, evaluation metrics).

| Agent | Purpose | Default tools |
|---|---|---|
| planner | Decompose objectives into ordered verifiable steps | — |
| research | Evidence gathering and source contrast | search_knowledge |
| retriever | Verbatim passage retrieval with sources | search_knowledge |
| compliance | GDPR / EU AI Act / DORA risk assessment | search_knowledge |
| security | OWASP-aligned vulnerability review | — |
| developer | Production-grade code generation | — |
| documentation | Technical writing | search_knowledge |
| reviewer | Code/design review | — |
| critic | Stress-testing of answers and plans | — |
| reporting | Executive summaries from raw findings | — |

Every run is bounded by `max_iterations` and `max_cost_usd`, logged to the audit trail, and
measured (task success, tool success, cost per task) by `evaluation/agent_eval.py`.
