# Enterprise AI Platform (EAP)

> A production-grade, self-hosted platform to **design, build, deploy, monitor and govern AI applications at scale** — RAG, AI Agents, LLMOps, MLOps and AI Governance in a single, provider-agnostic control plane.

[![CI](https://github.com/HadirouTamdamba/enterprise-ai-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/HadirouTamdamba/enterprise-ai-platform/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Why this platform exists

Enterprises (banks, insurers, hospitals, energy, government, manufacturing) want to industrialize AI, but face the same blockers:

| Blocker | Platform answer |
|---|---|
| Every team rebuilds LLM plumbing | Central **LLM Gateway** (11 providers, fallback, caching, rate limiting) |
| No cost visibility | **Token & cost tracking** per request, user, project, model |
| Ungoverned AI usage | **Governance Center**: model cards, risk register, approval workflows, audit logs |
| Untrusted answers | **Enterprise RAG** with hybrid search, re-ranking, citations, groundedness evaluation |
| Vendor lock-in | Hexagonal architecture — every provider is a replaceable adapter |
| No production monitoring | Prometheus / Grafana / Loki / OpenTelemetry built in |

## Core capabilities

- **LLM Gateway** — provider routing (Claude, GPT, Gemini, Mistral, Llama, DeepSeek, Ollama, OpenRouter, Azure OpenAI, AWS Bedrock, Vertex AI), fallback chains, retries, streaming, structured outputs, tool calling, semantic caching, rate limiting, cost/token accounting.
- **RAG Studio** — ingestion (PDF, DOCX, PPTX, XLSX, MD, CSV, JSON, HTML, images/OCR), configurable chunking (semantic/recursive/markdown/fixed), multi-provider embeddings, Qdrant vector store, hybrid search + metadata filtering, re-ranking, citation engine, feedback loop, document versioning.
- **Agent Orchestrator** — specialized agents (Planner, Research, Retriever, Compliance, Security, Developer, Documentation, Reviewer, Critic, Reporting) with tools, memory, planning, reflection and evaluation.
- **LLMOps** — prompt registry with versioning, prompt testing & evaluation, conversation memory, context compression, guardrails (prompt injection, PII, toxicity, hallucination detection), cost & latency analytics.
- **MLOps** — experiment tracking, dataset versioning, model registry, deployment strategies (shadow/canary), drift detection, retraining hooks, rollback.
- **Governance** — model cards, prompt cards, dataset cards, AI inventory, risk register, human approval workflow, compliance dashboard (GDPR, EU AI Act, DORA, ISO 42001 ready), immutable audit trail.
- **Enterprise foundation** — OAuth2/JWT auth, RBAC, organizations → workspaces → projects hierarchy, multi-tenancy, structured JSON logging, OpenTelemetry tracing, health/readiness probes.

## Architecture at a glance

```
┌────────────────────────────  Next.js Frontend  ───────────────────────────┐
│  Dashboard · RAG Studio · Prompt Playground · Monitoring · Governance     │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │ HTTPS (NGINX)
┌──────────────────────────────────▼─────────────────────────────────────────┐
│                        FastAPI Backend (/api/v1)                           │
│  Presentation → Application Services → Domain ← Infrastructure Adapters    │
│                                                                            │
│  LLM Gateway ─ RAG Engine ─ Agent Orchestrator ─ Prompt Registry ─ Gov.    │
└───┬──────────┬──────────┬──────────┬──────────┬──────────┬─────────────────┘
    │          │          │          │          │          │
PostgreSQL   Redis     Qdrant     Celery    MLflow    LLM Providers
(state)    (cache/RL) (vectors)  (workers) (registry) (Claude/GPT/…)
                                   Observability: Prometheus · Grafana · Loki · OTel
```

Full architecture: [docs/03-architecture.md](docs/03-architecture.md) — decisions: [docs/adr/](docs/adr/)

## Quick start (Docker Compose)

```bash
git clone https://github.com/HadirouTamdamba/enterprise-ai-platform.git
cd enterprise-ai-platform
cp .env.example .env          # add at least one LLM provider API key
make up                        # builds & starts the full stack
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API + OpenAPI docs | http://localhost:8000/api/v1/docs |
| Grafana | http://localhost:3001 (admin / admin) |
| Prometheus | http://localhost:9090 |
| Qdrant dashboard | http://localhost:6333/dashboard |

First admin user is seeded from `.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`).

## Local development

```bash
make install       # backend venv + frontend node_modules
make dev-backend   # uvicorn with reload (needs postgres/redis/qdrant: make up-deps)
make dev-frontend  # next dev
make test          # full test suite
make lint          # ruff + mypy + eslint
```

## Repository layout

```
backend/         FastAPI application (hexagonal architecture)
frontend/        Next.js 14 dashboard (TypeScript, Tailwind, shadcn/ui)
docker/          Dockerfiles
kubernetes/      K8s manifests (Kustomize)
terraform/       IaC modules (network, cluster, database, registry)
monitoring/      Prometheus, Grafana dashboards, Loki, alert rules
prompts/         Versioned prompt templates (YAML)
agents/          Agent role definitions
evaluation/      RAG / prompt / agent evaluation suites
tests/           Unit, integration, API, e2e, load, security tests
docs/            Business analysis, SRS, architecture, ADRs, guides, runbook
scripts/         Bootstrap, seed, backup utilities
.github/         CI/CD workflows
```

## Documentation

| Document | Purpose |
|---|---|
| [Business Analysis](docs/01-business-analysis.md) | Objectives, users, ROI, risks, KPIs |
| [Functional Specifications](docs/02-functional-specifications.md) | Feature catalogue & NFRs |
| [Architecture](docs/03-architecture.md) | C4 diagrams, data flows, AI/RAG/LLMOps architecture |
| [ADRs](docs/adr/) | Architecture decision records |
| [API Reference](docs/api.md) | Endpoint map, OpenAPI pointers, examples |
| [Deployment Guide](docs/deployment-guide.md) | Docker Compose, Kubernetes, Terraform |
| [Developer Guide](docs/developer-guide.md) | Codebase conventions, adding providers/agents |
| [Administrator Guide](docs/administrator-guide.md) | RBAC, tenants, quotas, governance |
| [User Guide](docs/user-guide.md) | RAG Studio, playground, agents |
| [Runbook](docs/runbook.md) | Operations, incidents, backup/restore |
| [Troubleshooting](docs/troubleshooting.md) | Common failures & fixes |
| [Production Readiness](docs/production-readiness-checklist.md) | Go-live checklist |

## Security & compliance

OAuth2 + JWT (access/refresh), RBAC (platform/org/workspace scopes), secrets via environment/secret manager, rate limiting, input & output validation, PII redaction guardrails, immutable audit log, TLS termination at NGINX. Compliance artifacts (model/dataset/prompt cards, risk register) are first-class API resources.

## License

MIT — see [LICENSE](LICENSE).
