# ADR-004: Celery + Redis for asynchronous pipelines

**Status:** Accepted · **Date:** 2026-07-16

## Context
Document ingestion (parse → OCR → chunk → embed → index), evaluation runs and retraining are
long-running and must not block API workers; they need retries, visibility and horizontal scaling.

## Decision
Use Celery with Redis broker/result backend. Task modules live in `app/workers/`. Tasks are
idempotent (keyed by document id + version) and emit progress to the documents table plus
Prometheus metrics.

## Consequences
+ Mature retry/queue semantics, easy autoscaling of workers, Flower/Grafana observability.
− Celery is sync-first; embedding calls inside tasks use dedicated event-loop helpers.
− Alternative (arq) would be lighter but lacks the operational tooling enterprises expect.
