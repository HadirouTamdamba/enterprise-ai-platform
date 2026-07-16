# ADR-003: Qdrant as default vector store behind a port

**Status:** Accepted · **Date:** 2026-07-16

## Context
Enterprise RAG needs payload filtering (workspace/document/version), hybrid search support,
self-hosting, and horizontal scalability. Candidates: Qdrant, pgvector, Milvus, Weaviate, Pinecone.

## Decision
Qdrant is the default adapter behind `VectorStorePort` (search, upsert, delete-by-filter,
collection lifecycle). pgvector remains a supported fallback adapter for teams that refuse a
second datastore; Pinecone/Weaviate can be added as adapters.

## Rationale
Qdrant offers HNSW performance, first-class payload indexing/filtering, snapshots, and an
Apache-2.0 license suitable for on-prem regulated deployments. pgvector simplifies ops but
degrades at high dimensionality/scale and lacks native hybrid scoring.

## Consequences
+ Workspace isolation via per-workspace collections + payload filters.
− One more stateful service to operate (covered by K8s StatefulSet + snapshots in the runbook).
