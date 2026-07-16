# Developer Guide

## Setup

```bash
make install        # backend venv + frontend node_modules
make up-deps        # postgres/redis/qdrant/monitoring via Docker
make migrate seed   # schema + admin user
make dev-backend    # uvicorn :8000 (OpenAPI at /api/v1/docs)
make dev-frontend   # next dev :3000
make test lint      # before every commit (pre-commit hooks: pre-commit install)
```

Tests are hermetic (SQLite, fake LLM, local embeddings, in-memory vectors) — no Docker needed
for `make test-backend`.

## Architecture rules (enforced in review)

- Dependency direction: `api → application → domain ← infrastructure/ai`.
- The **domain** layer never imports FastAPI, SQLAlchemy, Redis or any LLM SDK.
- Routes validate + delegate; business rules live in domain entities/services.
- All config through `app/core/config.py` (Pydantic Settings) — never `os.environ` directly.
- Raise typed exceptions from `app/core/exceptions.py`; the API layer maps them.
- No `print()` — use `get_logger(__name__)` (structured JSON with request context).
- Prompts belong in `prompts/*.yaml` or the Prompt Registry, never inline in code.

## Adding an LLM provider

1. Implement `LLMProviderPort` in `app/infrastructure/llm/providers.py`
   (OpenAI-compatible vendors only need a `OpenAICompatibleProvider(...)` entry).
2. Register it in `get_provider_registry()` (`app/infrastructure/llm/registry.py`).
3. Add pricing to `app/ai/gateway/pricing.py` (or `pricing_override.json` at runtime).
4. Add the API key field to `Settings` + `.env.example`.
5. Test with the playground: provider dropdown lists it automatically once configured.

## Adding an agent

1. Add the definition to `_AGENT_DEFINITIONS` in `app/ai/agents/catalog.py`.
2. Provide tools as `AgentTool` (typed JSON-Schema parameters + async handler) at the call
   site (`app/api/v1/agents.py`) or a shared tool module.
3. Add an evaluation task to `evaluation/agent_eval.py`.

## Adding a document format

1. Write `_parse_<fmt>()` in `app/infrastructure/ingestion/parsers.py` returning
   `[(page, text)]`, register the extension in the dispatch dict + `SUPPORTED_EXTENSIONS`.
2. Add a unit test with a fixture file.

## Database changes

```bash
cd backend
.venv/bin/alembic revision --autogenerate -m "add my_table"
.venv/bin/alembic upgrade head
```

Models live in `app/infrastructure/database/models.py` (UUID PKs, TimestampMixin, explicit
indexes). Add a repository method rather than querying from services.

## Conventions

Python 3.12+, full type hints, ruff + mypy strict, ≤100-char lines, functions ≤~40 lines.
Frontend: TypeScript strict, TanStack Query for server state, UI primitives in
`components/ui.tsx`. Commit style: `feat|fix|docs|chore(scope): imperative summary`.
