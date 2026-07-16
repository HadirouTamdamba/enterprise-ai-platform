# Operations Runbook

## Service map

| Component | Depends on | Impact when down |
|---|---|---|
| backend | postgres, redis, qdrant | Full API outage |
| worker | redis, postgres, qdrant | Ingestion stalls (uploads queue, no data loss) |
| frontend | backend | UI outage, API still serves |
| postgres | — | Full outage — restore priority 1 |
| redis | — | Rate limiting fails **open**, cache misses, Celery paused |
| qdrant | — | RAG queries fail; gateway/agents unaffected |
| LLM provider | — | Gateway falls back per routing chain; alert `LLMProviderFailures` |

## Daily checks
1. Grafana **AI Operations** dashboard: error rate < 1%, P95 gateway latency, cost/hour trend.
2. `GET /api/v1/health/ready` returns `ready`.
3. Pending governance approvals (`/governance/approvals?status=pending_review`) — SLA 2 business days.

## Alert response

| Alert | First actions |
|---|---|
| HighErrorRate | `kubectl -n eap logs deploy/backend --tail=200`, check recent deploys → rollback |
| HighApiLatency | Check DB connections + provider latency panels; scale backend if CPU-bound |
| LLMProviderFailures | Check provider status page; verify fallback chain is absorbing traffic; consider switching `DEFAULT_LLM_PROVIDER` |
| LLMCostSpike | `/api/v1/monitoring/costs` → identify project/model; apply budget or rate limit; notify owner |
| GuardrailBlocksSpike | Possible attack: pull audit log for the source user(s), disable accounts if confirmed |
| IngestionFailures | `kubectl -n eap logs deploy/worker`; common: unsupported/corrupt files, embedding provider down |

## Backup & restore
- **Backup:** `./scripts/backup.sh` (Postgres dump, Qdrant snapshot, uploads tar). Schedule daily; retain 30 days.
- **Restore Postgres:** `gunzip -c postgres.sql.gz | docker compose exec -T postgres psql -U eap eap`
- **Restore Qdrant:** upload snapshot via `/collections/{name}/snapshots/upload`, or re-index
  from source documents (`documents` table holds `storage_path` for every version).

## Scaling
- API: HPA handles CPU; for latency under token-heavy load raise `--workers` or replicas.
- Workers: scale on Celery queue depth (`celery -A app.workers.celery_app inspect active`).
- Qdrant: raise memory first (HNSW is RAM-bound); shard collections beyond ~5M vectors.

## Secret rotation
1. Create the new provider key at the vendor.
2. `kubectl -n eap create secret generic eap-secrets --from-literal=... --dry-run=client -o yaml | kubectl apply -f -`
3. `kubectl -n eap rollout restart deployment/backend deployment/worker`
4. Revoke the old key. JWT `SECRET_KEY` rotation invalidates all sessions — announce first.

## Monitoring reference
Prometheus metrics are prefixed `eap_` (HTTP, LLM tokens/cost/latency, RAG, agents,
guardrails, ingestion). Logs are structured JSON with `request_id`/`user_id` — correlate a
request across API and worker with one grep. Audit trail: `/api/v1/governance/audit`
(hash-chained; verify integrity by recomputing the chain).
