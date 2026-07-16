# ADR-001: Modular monolith over microservices

**Status:** Accepted · **Date:** 2026-07-16

## Context
The platform spans identity, LLM gateway, RAG, agents, MLOps and governance. Microservices would
add network hops, distributed transactions, and a service mesh to operate — heavy for a v1 that
must be easy to self-host in regulated environments.

## Decision
Ship a single FastAPI deployable with strict hexagonal module boundaries (`api → application →
domain ← infrastructure/ai`). Celery workers share the codebase but scale independently.

## Consequences
+ One image to secure, audit and deploy; simple local dev; transactional integrity in one DB.
+ Module seams (gateway, rag, agents) are extraction-ready if scale demands services later.
− Requires import-discipline enforcement (ruff isort rules + code review) to avoid coupling.
