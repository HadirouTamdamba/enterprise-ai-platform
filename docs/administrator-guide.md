# Administrator Guide

## Roles (RBAC)

| Role | Can |
|---|---|
| `viewer` | Read dashboards, query RAG, browse inventory |
| `analyst` | + Playground, agent runs |
| `engineer` | + Create projects, KBs, prompts, models; upload documents; request approvals |
| `compliance_officer` | + Review/decide approvals, read full audit trail |
| `workspace_admin` | + Manage a workspace |
| `org_admin` | + Manage users & workspaces in the organization |
| `platform_admin` | Everything, incl. creating organizations |

Assign via **Administration → Users** or `PATCH /api/v1/users/{id}` `{"role": "engineer"}`.
The first admin comes from `.env` (`ADMIN_EMAIL`/`ADMIN_PASSWORD`) — change the password
immediately after first login and keep at least two platform admins.

## Tenancy model

Organization → Workspaces → Projects. Vector data is isolated **per workspace**
(dedicated Qdrant collection); costs, prompts, KBs and models attach to **projects**.
Budgets: set `monthly_budget_usd` on organizations/projects; the `LLMCostSpike` alert and
cost dashboard track spend (hard cut-off is a org-level policy decision — see roadmap).

## Governance operations

- **Risk levels** follow the EU AI Act ladder: minimal / limited / high / prohibited.
- High-risk models cannot reach production without an **approved** review; requesters can
  never approve their own request (separation of duties, enforced server-side).
- Model/prompt/dataset cards are generated live from registry metadata — export via API.
- The audit trail is append-only and hash-chained; export regularly for evidence retention.

## Platform settings

All via environment (see `.env.example`): default/fallback models, RAG defaults
(chunk size, top-k, threshold, re-ranking), rate limits (requests/min and tokens/min),
upload cap (`MAX_UPLOAD_SIZE_MB`), CORS origins. Provider keys are secrets — rotate per
the runbook; the platform never returns them via any API.

## User lifecycle

Deactivate (never delete) users to preserve audit attribution:
`PATCH /api/v1/users/{id}` `{"is_active": false}` — tokens stop working at the next request.
