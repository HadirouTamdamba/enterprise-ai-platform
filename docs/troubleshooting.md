# Troubleshooting Guide

## Startup

| Symptom | Cause → Fix |
|---|---|
| `backend` restarts with settings validation error | `SECRET_KEY` missing/short in `.env` → set a 32+ char value |
| `/health/ready` says `database: unavailable` | Postgres not healthy yet → `docker compose ps`, check `POSTGRES_*` match between services |
| Frontend shows "Unable to reach the API" | `NEXT_PUBLIC_API_URL` wrong for the browser's network vantage point (it must be reachable from the user's machine, not the container) |
| Login fails with seeded admin | Seed ran before you edited `.env` → `docker compose run --rm seed` after fixing, or reset the volume |

## LLM Gateway

| Symptom | Cause → Fix |
|---|---|
| 502 `provider_unavailable` on every call | No provider key configured → check `GET /gateway/providers`; add a key and restart |
| Responses come from the fallback model | Primary provider erroring → check provider status page and `eap_llm_requests_total{outcome="error"}` |
| 400 `guardrail_violation` | Input matched injection/toxicity patterns → rephrase; if false positive, tune patterns in `app/ai/guardrails/pipeline.py` |
| 429 `rate_limit_exceeded` | Per-user request limit hit → raise `RATE_LIMIT_REQUESTS_PER_MINUTE` or investigate the client |
| Costs show $0 | Model missing from the pricing table → add it to `pricing.py`/`pricing_override.json` |

## RAG

| Symptom | Cause → Fix |
|---|---|
| Document stuck in `processing` | Worker down or broker unreachable → `docker compose logs worker`; re-upload retriggers |
| Document `failed`: "Event loop is closed" | Fixed — the worker now uses one persistent event loop per process. If seen on an older build, rebuild the worker: `docker compose up -d --build worker` |
| Document `failed`: "No text could be extracted" | Genuinely scanned/image PDF → text can't be extracted without OCR. Install the `ocr` extra + tesseract (see below), or convert to a text-based PDF |
| Empty answers / "could not find relevant information" | Threshold too strict or wrong KB → lower `similarity_threshold`, verify documents are `indexed` |
| Poor answer quality with no API keys | Local hash embeddings are lexical-only degraded mode → configure a real embedding provider |
| Answers cite stale content | Old version vectors not yet refreshed → re-upload completes the swap; check worker logs |

### Enabling OCR for scanned (image-based) PDFs

Text-based documents (PDF, DOCX, PPTX, XLSX, HTML, Markdown) index out of the box. Scanned
PDFs and images require OCR, which is an opt-in extra (keeps the default image slim):

1. Install the Python extra and system binaries in the worker image — add to
   `docker/worker.Dockerfile` before the `pip install`:
   ```dockerfile
   RUN apt-get update && apt-get install -y --no-install-recommends \
       tesseract-ocr tesseract-ocr-fra poppler-utils && rm -rf /var/lib/apt/lists/*
   ```
   and install the extra: `pip install ".[providers,ml,ocr]"`.
2. Rebuild: `docker compose up -d --build worker`.

The parsers already fall back to OCR automatically for pages with no extractable text.

## Kubernetes

| Symptom | Cause → Fix |
|---|---|
| Pods `CreateContainerConfigError` | `eap-secrets` missing → create it (see deployment guide §2) |
| Backend `CrashLoopBackOff` | `kubectl logs` — usually DB DNS/credentials; verify ConfigMap + Secret |
| Uploads PVC `Pending` | No RWX StorageClass → use EFS/Filestore/NFS class, or single-replica RWO |
| 413 on upload | Ingress body size → `proxy-body-size` annotation (set to 60m by default) |

## Tests & CI

| Symptom | Cause → Fix |
|---|---|
| `pytest` can't find `app` | Run from `backend/` with the venv, or `pip install -e .` first |
| Async fixture errors | Missing root `pytest.ini` (asyncio auto mode) — do not delete it |
| bcrypt `ValueError: password cannot be longer than 72 bytes` | You reintroduced passlib — the platform uses `bcrypt` directly (see security.py) |

Still stuck? Every response carries `x-request-id` — grep the structured logs for it:
`docker compose logs backend | grep <request_id>`.
