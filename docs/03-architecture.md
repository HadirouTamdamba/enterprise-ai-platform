# Technical Architecture — Enterprise AI Platform

**Version:** 1.0 · **Date:** 2026-07-16

## 1. System overview

EAP is a modular monolith backend (FastAPI) with async workers (Celery), a Next.js frontend, and a
hexagonal core that keeps business rules independent from every framework and AI vendor. It is
deployed as containers behind NGINX, with PostgreSQL (state), Redis (cache/queues/rate limits),
Qdrant (vectors), MLflow (ML registry) and a Prometheus/Grafana/Loki/OpenTelemetry observability
stack.

A modular monolith (not microservices) was chosen deliberately for v1: one deployable unit with
strict internal module boundaries gives enterprise-grade maintainability without the operational
cost of a service mesh. Boundaries are already aligned so that `llm_gateway`, `rag`, and `agents`
can be extracted into services later without touching the domain layer (see ADR-001).

## 2. C4 — Level 1: System context

```mermaid
C4Context
  Person(engineer, "AI Engineer", "Builds RAG apps, prompts, agents")
  Person(compliance, "Compliance Officer", "Reviews & approves AI assets")
  Person(exec, "Executive / CAIO", "Monitors adoption, cost, risk")
  System(eap, "Enterprise AI Platform", "Build, deploy, monitor, govern AI applications")
  System_Ext(llm, "LLM Providers", "Claude, GPT, Gemini, Mistral, Bedrock, Vertex, Ollama…")
  System_Ext(idp, "Enterprise IdP", "OIDC SSO")
  System_Ext(docs, "Document Sources", "SharePoint, S3, uploads")
  Rel(engineer, eap, "Uses API & dashboard")
  Rel(compliance, eap, "Approves, audits")
  Rel(exec, eap, "Views KPIs")
  Rel(eap, llm, "Inference via gateway adapters")
  Rel(eap, idp, "Federated login")
  Rel(docs, eap, "Document ingestion")
```

## 3. C4 — Level 2: Containers

```mermaid
C4Container
  Container(fe, "Frontend", "Next.js 14 / TypeScript", "Dashboard, RAG Studio, Playground, Governance")
  Container(nginx, "Edge", "NGINX", "TLS, routing, static caching")
  Container(api, "Backend API", "FastAPI / Python 3.12", "REST /api/v1, auth, business logic")
  Container(worker, "Async Workers", "Celery", "Ingestion, indexing, evaluation, retraining")
  ContainerDb(pg, "PostgreSQL 16", "State", "Users, projects, prompts, registry, audit")
  ContainerDb(redis, "Redis 7", "Cache", "Sessions, rate limits, semantic cache, queues")
  ContainerDb(qdrant, "Qdrant", "Vector DB", "Embeddings per workspace collection")
  Container(mlflow, "MLflow", "ML platform", "Experiments & model artifacts")
  Container(obs, "Observability", "Prometheus/Grafana/Loki/OTel", "Metrics, logs, traces")
  Rel(fe, nginx, "HTTPS")
  Rel(nginx, api, "HTTP")
  Rel(api, pg, "SQLAlchemy async")
  Rel(api, redis, "aioredis")
  Rel(api, qdrant, "gRPC/HTTP")
  Rel(api, worker, "Celery tasks via Redis")
  Rel(worker, qdrant, "Index chunks")
  Rel(api, mlflow, "Registry API")
```

## 4. C4 — Level 3: Backend components (hexagonal)

```
backend/app/
├── api/                    # PRESENTATION — routers, request/response schemas, deps
│   └── v1/  (auth, users, orgs, workspaces, projects, gateway, prompts,
│             knowledge_bases, documents, rag, conversations, agents,
│             models, experiments, deployments, governance, audit, monitoring, admin)
├── application/            # APPLICATION — use-case services, orchestration, transactions
├── domain/                 # DOMAIN — entities, value objects, business rules, ports (interfaces)
│   ├── entities/           #   pure dataclasses/pydantic — no framework imports
│   ├── ports/              #   LLMProviderPort, VectorStorePort, RepositoryPort, …
│   └── services/           #   pure business logic (routing policy, risk scoring, …)
├── infrastructure/         # INFRASTRUCTURE — adapters implementing ports
│   ├── database/           #   SQLAlchemy models, repositories, migrations, seed
│   ├── llm/                #   provider adapters (anthropic, openai, gemini, …)
│   ├── vector/             #   qdrant adapter (+ in-memory for tests)
│   ├── cache/              #   redis cache, rate limiter
│   ├── ingestion/          #   parsers (pdf, docx, pptx, xlsx, html, ocr…), chunkers
│   └── observability/      #   logging, metrics, tracing
├── ai/                     # AI LAYER — gateway, rag engine, agents, guardrails, evaluation
└── core/                   # SHARED — settings, security, exceptions, logging setup
```

**Dependency rule:** `api → application → domain ← infrastructure/ai`. The domain imports nothing
from FastAPI, SQLAlchemy, Redis or any LLM SDK.

## 5. Key sequence — RAG query with governance

```mermaid
sequenceDiagram
  participant U as User
  participant API as FastAPI /rag/query
  participant G as Guardrails
  participant R as Retriever
  participant Q as Qdrant
  participant GW as LLM Gateway
  participant P as Provider (Claude → fallback GPT)
  participant A as Audit Log
  U->>API: question + kb_id (JWT)
  API->>G: validate input (injection, PII)
  G-->>API: ok / redacted
  API->>R: hybrid retrieve(top_k, filters)
  R->>Q: vector + keyword search
  Q-->>R: chunks + scores
  R-->>API: re-ranked context
  API->>GW: prompt(assembled context)
  GW->>P: chat completion (stream)
  P-->>GW: answer + usage
  GW-->>API: answer, tokens, cost
  API->>G: output check (groundedness, PII)
  API->>A: audit event (user, kb, cost, citations)
  API-->>U: answer + citations + confidence
```

## 6. Data flow — document ingestion

Upload → virus/size/type validation → object storage (`data/uploads`) → Celery task:
parse (format-specific parser, OCR fallback) → clean → chunk (strategy from KB config) →
embed (batch, provider adapter) → upsert to Qdrant (payload: doc id, version, page, metadata) →
mark document `indexed` → emit metrics + audit event. Re-ingestion bumps `version`; stale
vectors for old versions are deleted after successful reindex ("knowledge refresh").

## 7. AI architecture

- **LLM Gateway** (`ai/gateway`): single `ChatRequest → ChatResponse` contract. A routing policy
  (domain service) picks provider/model from: explicit request → project default → platform
  default. Failures cascade through the fallback chain with exponential backoff. Every call emits
  usage records (tokens, USD, latency) and Prometheus metrics; responses are cached (exact-match +
  optional semantic) in Redis.
- **Provider adapters** implement `LLMProviderPort` (chat, stream, embed where supported); pricing
  tables are configuration, not code.
- **Guardrails** run as pre/post pipelines: prompt-injection heuristics, PII regex+NER redaction,
  toxicity filter, JSON-schema output validation, groundedness check (citation overlap + LLM judge).
- **Agents** (`ai/agents`): declarative `AgentSpec` (role, system prompt ref, tools, memory,
  budget). Orchestrator executes plan → act → reflect with hard guards (max iterations, max cost).
  Tools are typed, validated, and every execution is logged.
- **Evaluation** (`evaluation/`): dataset-driven suites for prompts (assertions + LLM judge), RAG
  (faithfulness, relevance, context precision/recall) and agents (task/tool success), runnable in
  CI and persisted for trend dashboards.

## 8. Security architecture

TLS at NGINX → JWT (HS256, short-lived access + rotating refresh) → RBAC dependency on every
route (scope = platform/org/workspace/project) → Pydantic validation on all inputs → rate limiting
(Redis sliding window, request- and token-based) → secrets only via environment/secret manager →
structured logs with secret/PII redaction → immutable audit table (append-only, hash-chained) →
OWASP Top 10 review in CI (bandit, dependency audit).

## 9. Deployment architecture

- **Docker Compose** — full stack for evaluation/dev (single host).
- **Kubernetes** — production: Deployments (api ×3, worker ×2, frontend ×2), StatefulSets
  (postgres, qdrant), HPA on api/worker, PodDisruptionBudgets, NetworkPolicies, Ingress-NGINX,
  secrets via `Secret`/external-secrets, probes wired to `/health/live` and `/health/ready`.
- **Terraform** — modules for network, managed Postgres, Kubernetes cluster, container registry,
  DNS; cloud-agnostic layout with AWS reference implementation.

## 10. Technology choices & trade-offs (summary)

| Choice | Why | Trade-off accepted |
|---|---|---|
| Modular monolith | Fast delivery, simple ops, clear seams | Requires discipline on module boundaries (enforced by import rules) |
| FastAPI + Pydantic v2 | Async, typed, OpenAPI for free | — |
| PostgreSQL | ACID, JSONB for flexible metadata, ubiquitous | — |
| Qdrant | Fast HNSW, payload filtering, hybrid support, self-hosted | Second datastore to operate (behind `VectorStorePort`, swappable to pgvector) |
| Redis | Cache + rate limit + Celery broker in one | Single point — mitigated by K8s HA setup |
| Celery | Mature, observable async jobs | Heavier than arq/BackgroundTasks; justified by ingestion volume |
| MLflow | De-facto standard registry/tracking | Separate UI; integrated via API + links |
| Next.js 14 App Router | SSR dashboard, TS end-to-end | — |

Decisions are individually recorded in [ADRs](adr/).
