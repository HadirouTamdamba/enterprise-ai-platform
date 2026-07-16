# API Reference

Interactive OpenAPI documentation is generated from code: **`/api/v1/docs`** (Swagger UI)
and `/api/v1/openapi.json`. All endpoints require `Authorization: Bearer <access_token>`
except registration, login, refresh and health probes. Errors are standardized:
`{"code", "message", "details", "request_id"}`.

## Endpoint map

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register` · `POST /auth/login` (OAuth2 form) · `POST /auth/refresh` · `GET /auth/me` |
| Tenancy | `GET/POST /organizations` · `GET/POST /workspaces` · `GET/POST /projects` · `GET /projects/{id}` |
| Users | `GET /users` · `PATCH /users/{id}` |
| LLM Gateway | `GET /gateway/providers` · `POST /gateway/chat` (set `"stream": true` for SSE) |
| Prompts | `GET/POST /prompts` · `GET/POST /prompts/{id}/versions` · `POST /prompts/{id}/versions/{n}/activate` |
| RAG | `GET/POST /rag/knowledge-bases` · `POST /rag/knowledge-bases/{id}/documents` (multipart) · `GET …/documents` · `POST /rag/query` · `POST /rag/feedback` |
| Agents | `GET /agents` · `POST /agents/run` |
| Governance | `GET/POST /governance/models` · `POST /governance/models/{id}/promote\|rollback` · `GET /governance/models/{id}/card` · `GET/POST /governance/approvals` · `POST /governance/approvals/{id}/decide` · `GET /governance/audit` · `GET /governance/inventory` |
| Monitoring | `GET /monitoring/usage` · `GET /monitoring/usage/by-model` · `GET /monitoring/costs` |
| Health | `GET /health` · `GET /health/live` · `GET /health/ready` · `GET /metrics` (Prometheus, internal) |

## Quick example

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -d "username=admin@example.com&password=ChangeMe123!" | jq -r .access_token)

curl -s localhost:8000/api/v1/gateway/chat \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say hello"}]}' | jq
```

A complete Python walkthrough (login → KB → upload → RAG query → cost check) lives in
[`examples/api_usage.py`](../examples/api_usage.py).
