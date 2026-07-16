# Production Readiness Checklist

**Status:** platform-level items verified in this repository ✅ · deployment-level items
(marked ☐) are per-installation and must be checked at go-live.

## Code & quality
- ✅ Hexagonal architecture, typed end-to-end (ruff + mypy strict configuration)
- ✅ 50 automated tests passing (unit, integration, API, security behaviors, RAG e2e)
- ✅ AI evaluation suites gate CI (RAG retrieval, guardrails, agents) with thresholds
- ✅ Bandit security scan clean; pre-commit hooks configured
- ✅ No hardcoded secrets, models or endpoints — configuration only

## Security
- ✅ JWT access/refresh with rotation, bcrypt(12) hashing, generic auth errors
- ✅ RBAC on every route; separation of duties in approvals
- ✅ Input validation (Pydantic) + guardrails (injection, PII, toxicity) + output checks
- ✅ Rate limiting (request + token), upload validation (type, size, path-safe names)
- ✅ Secrets via env/secret manager; log redaction; non-root containers
- ✅ Hash-chained append-only audit trail
- ☐ TLS certificates issued and enforced end-to-end
- ☐ Penetration test against the staging deployment
- ☐ SSO/OIDC federation to the enterprise IdP configured

## Reliability
- ✅ Health/readiness/liveness probes wired to orchestrator
- ✅ LLM fallback chains + retries; Redis fail-open; graceful degradation paths
- ✅ HPA (api 3→10, workers 2→8), PodDisruptionBudget, idempotent ingestion
- ☐ Backup schedule active and **restore rehearsed** (`scripts/backup.sh`)
- ☐ Load test executed against staging (`tests/load/locustfile.py`) at expected traffic

## Observability
- ✅ RED metrics + AI metrics (tokens, cost, latency, cache, guardrails, agents)
- ✅ Grafana dashboard provisioned; 6 alert rules incl. cost spike & injection attack
- ✅ Structured JSON logs with request/user correlation
- ☐ Alerts routed to the on-call channel (Alertmanager receiver)

## Governance & compliance
- ✅ AI inventory, model/prompt/dataset cards from live metadata
- ✅ EU AI Act risk ladder; human approval gate enforced for high-risk production deploys
- ✅ Model rollback path; prompt version rollback
- ☐ DPIA / records of processing completed for the hosting context
- ☐ Retention & erasure policies configured to local regulation

## Documentation
- ✅ Business analysis, SRS, architecture + ADRs, deployment, runbook, developer,
  administrator, user, troubleshooting, API — all in `docs/`
- ✅ OpenAPI generated from code; runnable example in `examples/`

**Go-live rule:** every ☐ item above must be checked and signed off by the platform owner,
CISO and DPO before production traffic.
