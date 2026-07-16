"""Embedding providers (F-23). OpenAI-compatible HTTP adapter + deterministic local fallback."""

import hashlib
import math

import httpx

from app.core.config import get_settings
from app.core.exceptions import ModelInferenceError
from app.domain.ports.llm import EmbeddingProviderPort


class OpenAICompatibleEmbeddings(EmbeddingProviderPort):
    """Works for OpenAI, Mistral, Ollama and any /v1/embeddings-compatible endpoint."""

    def __init__(self, name: str, api_key: str, base_url: str, requires_key: bool = True) -> None:
        self.name = name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._requires_key = requires_key

    def available(self) -> bool:
        return bool(self._api_key) or not self._requires_key

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        headers = {"content-type": "application/json"}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/embeddings",
                headers=headers,
                json={"model": model, "input": texts},
            )
        if response.status_code >= 400:
            raise ModelInferenceError(
                f"Embedding provider '{self.name}' failed (HTTP {response.status_code})"
            )
        data = response.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda d: d["index"])]


class LocalHashEmbeddings(EmbeddingProviderPort):
    """Deterministic, dependency-free embeddings.

    DEGRADED MODE ONLY: enables keyless demos and offline tests. Vectors capture
    token-level lexical similarity, not semantics — production deployments must
    configure a real embedding provider.
    """

    name = "local"

    def __init__(self, dimension: int = 1536) -> None:
        self._dimension = dimension

    def available(self) -> bool:
        return True

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in text.lower().split():
            digest = hashlib.md5(token.encode(), usedforsecurity=False).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


def get_embedding_provider(name: str | None = None) -> EmbeddingProviderPort:
    """Resolve the configured embedding provider, degrading to local hashing."""
    s = get_settings()
    name = name or s.default_embedding_provider
    candidates: dict[str, EmbeddingProviderPort] = {
        "openai": OpenAICompatibleEmbeddings("openai", s.openai_api_key, "https://api.openai.com/v1"),
        "mistral": OpenAICompatibleEmbeddings("mistral", s.mistral_api_key, "https://api.mistral.ai/v1"),
        "ollama": OpenAICompatibleEmbeddings("ollama", "", f"{s.ollama_base_url}/v1", requires_key=False),
        "local": LocalHashEmbeddings(s.embedding_dimension),
    }
    provider = candidates.get(name)
    if provider is not None and provider.available():
        return provider
    return LocalHashEmbeddings(s.embedding_dimension)
