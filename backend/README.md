# Enterprise AI Platform — Backend

FastAPI backend implementing the platform's hexagonal core: identity & tenancy, LLM gateway,
RAG engine, agent orchestrator, governance and monitoring APIs.

See the [root README](../README.md) for the full platform documentation and quick start.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload      # API on :8000, docs at /api/v1/docs
.venv/bin/pytest ../tests/backend -v         # test suite (no network required)
```
