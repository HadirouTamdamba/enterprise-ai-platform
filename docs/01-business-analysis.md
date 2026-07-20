# Business Analysis — Enterprise AI Platform (EAP)

**Version:** 1.0 · **Date:** 2026-07-16 · **Status:** Approved · **Owner:** Hadirou Tamdamba

## 1. Executive summary

Enterprises are adopting generative AI faster than they can govern it. Individual teams build
isolated chatbots and RAG prototypes with duplicated plumbing, unmanaged costs, no evaluation
discipline and no compliance trail. The Enterprise AI Platform (EAP) is a **self-hosted control
plane** that centralizes LLM access, RAG application building, agent orchestration, ML lifecycle
management and AI governance behind one secure, multi-tenant API and dashboard.

## 2. Business objective

Provide a single platform on which enterprise teams can **develop, deploy, monitor and govern AI
applications** — reducing time-to-production for an AI use case from months to days while keeping
cost, risk and compliance under central control.

## 3. End users & stakeholders

| Persona | Needs |
|---|---|
| Chief AI Officer | Portfolio view, AI inventory, risk posture, cost control |
| AI / GenAI Engineers | LLM gateway, RAG studio, prompt tooling, agent framework |
| ML Engineers / Data Scientists | Experiment tracking, model registry, deployment, drift monitoring |
| Data Engineers | Document/dataset ingestion, versioning, pipelines |
| Software Engineers | Stable, versioned inference APIs with SDK-friendly contracts |
| DevOps / SRE | Containerized deployment, observability, runbooks, autoscaling |
| Compliance Officers | Model cards, audit logs, approval workflows, EU AI Act artifacts |
| Executives | Business KPIs: adoption, cost per use case, ROI dashboards |

**Stakeholders:** CIO/CTO (sponsorship), CISO (security sign-off), Data Protection Officer (GDPR),
Risk & Legal (AI Act classification), business unit leaders (use-case demand).

## 4. Business value & expected ROI

- **Engineering leverage:** shared LLM gateway + RAG platform removes ~60–80% of duplicated
  integration work per use case (industry-typical estimate for platform consolidation).
- **Cost control:** central token/cost accounting and semantic caching typically reduce LLM spend
  15–40% versus uncontrolled direct API usage.
- **Risk reduction:** approval workflows and audit trails avoid regulatory findings (EU AI Act
  fines up to 7% of global turnover for prohibited practices; 3% for other violations).
- **Speed:** a governed RAG assistant can be assembled from existing components in < 1 day.

## 5. Constraints

- **Technical:** self-hostable (on-prem or any cloud); no hard dependency on a single LLM vendor;
  Python 3.12 / FastAPI backend, Next.js frontend per enterprise stack standards.
- **Regulatory:** GDPR by design; EU AI Act readiness; sector overlays (DORA/CSSF for finance,
  HIPAA-equivalent controls for healthcare, NIS2 for energy).
- **Operational:** must run on commodity Kubernetes; observability mandatory from day one.

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM provider outage | Medium | High | Multi-provider gateway with fallback chains |
| Hallucinated answers reach users | Medium | High | Groundedness evaluation, citations, guardrails, human approval for high-risk apps |
| Cost overrun on tokens | High | Medium | Budgets, quotas, rate limits, caching, per-project cost dashboards |
| PII leakage into prompts/logs | Medium | High | PII detection guardrail, log redaction, encryption |
| Vendor lock-in | Medium | Medium | Hexagonal architecture; providers are adapters |
| Regulatory non-compliance | Low | High | Governance module produces required artifacts continuously |
| Vector index drift vs. source docs | Medium | Medium | Document versioning + scheduled knowledge refresh |

## 7. Assumptions

1. Customers provide their own LLM API keys or on-prem models (Ollama).
2. Initial deployment targets a single region; multi-region HA is a roadmap item.
3. SSO federation (OIDC) integrates with the customer IdP; local accounts are the fallback.
4. Document volumes up to ~1M chunks per workspace in v1 (Qdrant single cluster).

## 8. Success criteria & KPIs

| KPI | Target |
|---|---|
| Time to deploy a new governed RAG app | < 1 day |
| API availability | ≥ 99.9% |
| P95 gateway overhead latency | < 150 ms (excluding model inference) |
| LLM cost visibility | 100% of calls attributed to project & user |
| Groundedness score on evaluation set | ≥ 0.85 |
| Audit coverage | 100% of AI interactions logged |
| Test coverage (backend core) | ≥ 80% |

## 9. Compliance requirements

GDPR (data minimization, right to erasure, records of processing), EU AI Act (risk classification,
technical documentation, logging, human oversight), ISO 27001/42001 alignment, DORA/CSSF overlays
for financial deployments. The Governance Center produces model cards, dataset cards, prompt cards,
a risk register and exportable audit reports as first-class platform features.
