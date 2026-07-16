"""RAG evaluation (F-27): retrieval hit rate, context precision, groundedness.

Runs fully offline (local embeddings + in-memory vector store) so it can gate CI.
With provider keys configured, the same harness measures the production embedding
model instead — set EVAL_EMBEDDING_PROVIDER.

Usage: python -m evaluation.rag_eval  (from backend/ with the venv active)
"""

import asyncio
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "evaluation-only-secret-0123456789")
os.environ.setdefault("DEFAULT_EMBEDDING_PROVIDER", os.getenv("EVAL_EMBEDDING_PROVIDER", "local"))
os.environ.setdefault("EMBEDDING_DIMENSION", "256")

from app.ai.guardrails.pipeline import groundedness_score  # noqa: E402
from app.ai.rag.embeddings import get_embedding_provider  # noqa: E402
from app.domain.ports.vector_store import VectorRecord  # noqa: E402
from app.infrastructure.vector.qdrant_store import InMemoryVectorStore  # noqa: E402

DATASET = Path(__file__).parent / "datasets" / "rag_golden.json"
THRESHOLDS = {"retrieval_hit_rate": 0.66, "keyword_recall": 0.5}


async def evaluate() -> dict:
    data = json.loads(DATASET.read_text())
    embedder = get_embedding_provider()
    store = InMemoryVectorStore()
    await store.ensure_collection("eval", 256)

    texts = [doc["text"] for doc in data["corpus"]]
    vectors = await embedder.embed(texts, "eval-model")
    await store.upsert(
        "eval",
        [
            VectorRecord(id=doc["id"], vector=vec, payload={"content": doc["text"], "id": doc["id"]})
            for doc, vec in zip(data["corpus"], vectors, strict=True)
        ],
    )

    hits = 0
    keyword_scores: list[float] = []
    groundedness: list[float] = []
    for case in data["cases"]:
        query_vec = (await embedder.embed([case["question"]], "eval-model"))[0]
        results = await store.search("eval", query_vec, top_k=2)
        retrieved_ids = [r.payload["id"] for r in results]
        if case["expected_source"] in retrieved_ids:
            hits += 1
        context = " ".join(r.payload["content"] for r in results).lower()
        matched = sum(1 for kw in case["expected_keywords"] if kw.lower() in context)
        keyword_scores.append(matched / len(case["expected_keywords"]))
        groundedness.append(groundedness_score(context[:200], [context]))

    report = {
        "cases": len(data["cases"]),
        "retrieval_hit_rate": round(hits / len(data["cases"]), 3),
        "keyword_recall": round(sum(keyword_scores) / len(keyword_scores), 3),
        "avg_context_groundedness": round(sum(groundedness) / len(groundedness), 3),
        "embedding_provider": embedder.name,
    }
    report["passed"] = all(report[k] >= v for k, v in THRESHOLDS.items())
    return report


if __name__ == "__main__":
    result = asyncio.run(evaluate())
    print(json.dumps(result, indent=2))  # noqa: T201 — CLI entrypoint
    sys.exit(0 if result["passed"] else 1)
