"""Vector store port — keeps business logic independent from Qdrant/pgvector/etc. (ADR-003)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class VectorRecord:
    id: str
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VectorHit:
    id: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


class VectorStorePort(ABC):
    @abstractmethod
    async def ensure_collection(self, name: str, dimension: int) -> None: ...

    @abstractmethod
    async def upsert(self, collection: str, records: list[VectorRecord]) -> None: ...

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        top_k: int = 8,
        score_threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]: ...

    @abstractmethod
    async def delete_by_filter(self, collection: str, filters: dict[str, Any]) -> None: ...

    @abstractmethod
    async def drop_collection(self, name: str) -> None: ...
