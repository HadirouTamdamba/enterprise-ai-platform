# Production Readiness Checklist

**Status:** platform-level items verified in this repository; deployment-level items
(marked `[ ]`) are per-installation and must be checked at go-live.

## Code & quality
- [x] Hexagonal architecture, typed end-to-end (ruff + mypy strict configuration)
- [x] 50 automated tests passing (unit, integration, API, security behaviors, RAG e2e)
- [x] AI evaluation suites gate CI (RAG retrieval, guardrails, agents) with thresholds
- [x] Bandit security scan clean; pre-commit hooks configured
- [x] No hardcoded secrets, models or endpoints - configuration only

## Security
- [x] JWT access/refresh with rotation, bcrypt(12) hashing, generic auth errors
- [x] RBAC on every route; separation of duties in approvals
- [x] Input validation (Pydantic) + guardrails (injection, PII, toxicity) + output checks
- [x] Rate limiting (request + token), upload validation (type, size, path-safe names)
- [x] Secrets via env/secret manager; log redaction; non-root containers
- [x] Hash-chained append-only audit trail
- [ ] TLS certificates issued and enforced end-to-end
- [ ] Penetration test against the staging deployment
- [ ] SSO/OIDC federation to the enterprise IdP configured

## Reliability
- [x] Health/readiness/liveness probes wired to orchestrator
- [x] LLM fallback chains + retries; Redis fail-open; graceful degradation paths
- [x] HPA (api 3->10, workers 2->8), PodDisruptionBudget, idempotent ingestion
- [ ] Backup schedule active and **restore rehearsed** (`scripts/backup.sh`)
- [ ] Load test executed against staging (`tests/load/locustfile.py`) at expected traffic

## Observability
- [x] RED metrics + AI metrics (tokens, cost, latency, cache, guardrails, agents)
- [x] Grafana dashboard provisioned; 6 alert rules incl. cost spike & injection attack
- [x] Structured JSON logs with request/user correlation
- [ ] Alerts routed to the on-call channel (Alertmanager receiver)

## Governance & compliance
- [x] AI inventory, model/prompt/dataset cards from live metadata
- [x] EU AI Act risk ladder; human approval gate enforced for high-risk production deploys
- [x] Model rollback path; prompt version rollback
- [ ] DPIA / records of processing completed for the hosting context
- [ ] Retention & erasure policies configured to local regulation

## Documentation
- [x] Business analysis, SRS, architecture + ADRs, deployment, runbook, developer,
  administrator, user, troubleshooting, API - all in `docs/`
- [x] OpenAPI generated from code; runnable example in `examples/`

**Go-live rule:** every `[ ]` item above must be checked and signed off by the platform owner,
CISO and DPO before production traffic.
