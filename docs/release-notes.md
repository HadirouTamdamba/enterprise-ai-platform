# Release Notes

## v1.0.0 — 2026-07-16

First production-ready release of the Enterprise AI Platform.

### Highlights
- **LLM Gateway** — 11 providers behind one contract; routing, fallback, retries,
  caching, streaming, structured outputs, full token & cost accounting.
- **Enterprise RAG** — 10+ document formats (incl. OCR), 4 chunking strategies,
  hybrid retrieval with re-ranking, citations, groundedness scoring, document
  versioning with knowledge refresh, feedback loop.
- **Multi-agent platform** — 10 specialized agents with planning, tools, reflection,
  iteration & cost budgets, full execution tracing.
- **LLMOps** — prompt registry with versioning & instant rollback, guardrails
  (injection, PII, toxicity), conversation memory, cost/latency analytics.
- **MLOps** — model registry with stages, approval-gated promotion, one-click rollback,
  MLflow integration point.
- **Governance** — AI inventory, live model cards, EU AI Act risk levels,
  human-in-the-loop approvals with separation of duties, hash-chained audit trail.
- **Enterprise foundation** — multi-tenant (org/workspace/project), RBAC (7 roles),
  JWT auth, rate limiting, structured logging, Prometheus/Grafana/Loki observability.
- **Delivery** — Docker Compose one-command stack, Kubernetes manifests with HPA and
  NetworkPolicies, Terraform AWS reference, CI/CD with AI-evaluation quality gates.

### Known limitations (v1)
- Gemini streaming is buffered (single flush) pending native SSE adapter.
- Bedrock/Vertex adapters use their OpenAI-compatible gateways; native SigV4/OAuth
  adapters are on the roadmap.
- Semantic chunking is sentence-heuristic (embedding-based splitter on roadmap).
- Budget enforcement is alert-based; hard per-project cut-offs planned for v1.1.

### Roadmap (v1.1+)
OIDC SSO federation · notification center UI · MLflow deep-linking in the frontend ·
cross-encoder re-ranker adapter · drift-triggered retraining pipelines · multi-region HA.
