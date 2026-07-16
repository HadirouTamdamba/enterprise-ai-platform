"""Qdrant adapter for VectorStorePort (ADR-003) + in-memory adapter for tests."""

import math
from typing import Any

from app.domain.ports.vector_store import VectorHit, VectorRecord, VectorStorePort


class QdrantVectorStore(VectorStorePort):
    def __init__(self, host: str, port: int) -> None:
        from qdrant_client import AsyncQdrantClient

        self._client = AsyncQdrantClient(host=host, port=port)

    async def ensure_collection(self, name: str, dimension: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        if not await self._client.collection_exists(name):
            await self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )

    async def upsert(self, collection: str, records: list[VectorRecord]) -> None:
        from qdrant_client.models import PointStruct

        await self._client.upsert(
            collection_name=collection,
            points=[
                PointStruct(id=r.id, vector=r.vector, payload=r.payload) for r in records
            ],
        )

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        top_k: int = 8,
        score_threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_filter = None
        if filters:
            query_filter = Filter(
                must=[
                    FieldCondition(key=key, match=MatchValue(value=value))
                    for key, value in filters.items()
                ]
            )
        if hasattr(self._client, "query_points"):  # qdrant-client >= 1.10
            response = await self._client.query_points(
                collection_name=collection,
                query=query_vector,
                limit=top_k,
                score_threshold=score_threshold or None,
                query_filter=query_filter,
                with_payload=True,
            )
            points = response.points
        else:  # legacy API (qdrant-client 1.9)
            points = await self._client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=score_threshold or None,
                query_filter=query_filter,
                with_payload=True,
            )
        return [VectorHit(id=str(p.id), score=p.score, payload=p.payload or {}) for p in points]

    async def delete_by_filter(self, collection: str, filters: dict[str, Any]) -> None:
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        await self._client.delete(
            collection_name=collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(key=key, match=MatchValue(value=value))
                        for key, value in filters.items()
                    ]
                )
            ),
        )

    async def drop_collection(self, name: str) -> None:
        if await self._client.collection_exists(name):
            await self._client.delete_collection(name)


class InMemoryVectorStore(VectorStorePort):
    """Deterministic vector store for unit tests and keyless demos."""

    def __init__(self) -> None:
        self._collections: dict[str, dict[str, VectorRecord]] = {}

    async def ensure_collection(self, name: str, dimension: int) -> None:
        self._collections.setdefault(name, {})

    async def upsert(self, collection: str, records: list[VectorRecord]) -> None:
        store = self._collections.setdefault(collection, {})
        for record in records:
            store[record.id] = record

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        top_k: int = 8,
        score_threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        hits: list[VectorHit] = []
        for record in self._collections.get(collection, {}).values():
            if filters and any(record.payload.get(k) != v for k, v in filters.items()):
                continue
            score = _cosine(query_vector, record.vector)
            if score >= score_threshold:
                hits.append(VectorHit(id=record.id, score=score, payload=record.payload))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    async def delete_by_filter(self, collection: str, filters: dict[str, Any]) -> None:
        store = self._collections.get(collection, {})
        to_delete = [
            record_id
            for record_id, record in store.items()
            if all(record.payload.get(k) == v for k, v in filters.items())
        ]
        for record_id in to_delete:
            del store[record_id]

    async def drop_collection(self, name: str) -> None:
        self._collections.pop(name, None)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


_store: VectorStorePort | None = None


def get_vector_store() -> VectorStorePort:
    """Vector store singleton — Qdrant in normal operation, in-memory for tests."""
    global _store
    if _store is None:
        from app.core.config import get_settings

        settings = get_settings()
        if settings.environment == "test":
            _store = InMemoryVectorStore()
        else:
            _store = QdrantVectorStore(settings.qdrant_host, settings.qdrant_port)
    return _store
