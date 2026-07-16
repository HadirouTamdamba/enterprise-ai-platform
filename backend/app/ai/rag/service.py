"""RAG engine (F-20..F-29): ingestion, hybrid retrieval, re-ranking, citations,
guarded generation with groundedness confidence."""

import re
import uuid
from pathlib import Path
from uuid import UUID

from app.ai.gateway.service import LLMGatewayService
from app.ai.guardrails.pipeline import groundedness_score, validate_input, validate_output
from app.ai.rag.chunking import chunk_text
from app.ai.rag.embeddings import get_embedding_provider
from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.entities.ai import ChunkingStrategy, Citation, DocumentStatus
from app.domain.ports.llm import ChatMessage, ChatRequest, MessageRole
from app.domain.ports.vector_store import VectorHit, VectorRecord, VectorStorePort
from app.infrastructure.database.models import DocumentModel, KnowledgeBaseModel
from app.infrastructure.ingestion.parsers import parse_document
from app.infrastructure.observability.metrics import (
    DOCUMENTS_INDEXED,
    RAG_QUERIES,
    RAG_RETRIEVED_CHUNKS,
)

logger = get_logger(__name__)

_RAG_SYSTEM_PROMPT = """You are an enterprise knowledge assistant.
Answer the user's question using ONLY the numbered context passages below.
Rules:
- Cite passages inline as [1], [2] matching the passage numbers you used.
- If the context does not contain the answer, say so explicitly — never invent facts.
- Be concise and factual. Answer in the language of the question.

Context passages:
{context}"""


def collection_for_workspace(workspace_id: UUID) -> str:
    prefix = get_settings().qdrant_collection_prefix
    return f"{prefix}_ws_{workspace_id.hex}"


class RAGService:
    def __init__(self, vector_store: VectorStorePort, gateway: LLMGatewayService) -> None:
        self._vectors = vector_store
        self._gateway = gateway

    # ------------------------------------------------------------------ ingest
    async def ingest_document(
        self, document: DocumentModel, kb: KnowledgeBaseModel
    ) -> int:
        """Parse → chunk → embed → index. Returns the number of chunks indexed.

        Idempotent per (document, version): previous vectors for the same
        filename are removed first (document versioning / knowledge refresh).
        """
        settings = get_settings()
        collection = collection_for_workspace(kb.workspace_id)
        embedder = get_embedding_provider(kb.embedding_provider or None)
        model = kb.embedding_model or settings.default_embedding_model

        pages = parse_document(Path(document.storage_path), document.content_type)
        chunks = []
        for page, text in pages:
            chunks.extend(
                chunk_text(
                    text,
                    strategy=ChunkingStrategy(kb.chunking_strategy),
                    chunk_size=kb.chunk_size,
                    chunk_overlap=kb.chunk_overlap,
                    page=page,
                )
            )
        if not chunks:
            raise ValueError("No text could be extracted from the document")

        await self._vectors.ensure_collection(collection, settings.embedding_dimension)
        # Knowledge refresh: drop vectors of previous versions of this file.
        await self._vectors.delete_by_filter(collection, {"filename": document.filename})

        texts = [c.content for c in chunks]
        vectors = []
        batch_size = 64
        for start in range(0, len(texts), batch_size):
            vectors.extend(await embedder.embed(texts[start : start + batch_size], model))

        records = [
            VectorRecord(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "document_id": str(document.id),
                    "knowledge_base_id": str(document.knowledge_base_id),
                    "filename": document.filename,
                    "chunk_index": chunk.index,
                    "page": chunk.page,
                    "document_version": document.version,
                    "embedding_version": kb.embedding_version,
                    "content": chunk.content,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await self._vectors.upsert(collection, records)
        DOCUMENTS_INDEXED.labels("success").inc()
        logger.info(
            "document_indexed", document=str(document.id), chunks=len(records), kb=str(kb.id)
        )
        return len(records)

    # ----------------------------------------------------------------- retrieve
    async def retrieve(
        self,
        kb: KnowledgeBaseModel,
        question: str,
        *,
        top_k: int | None = None,
        filters: dict | None = None,
    ) -> list[VectorHit]:
        """Hybrid retrieval: vector search + lexical keyword boost, then re-rank."""
        settings = get_settings()
        collection = collection_for_workspace(kb.workspace_id)
        embedder = get_embedding_provider(kb.embedding_provider or None)
        model = kb.embedding_model or settings.default_embedding_model
        k = top_k or kb.top_k

        query_vector = (await embedder.embed([question], model))[0]
        combined_filters = {"knowledge_base_id": str(kb.id), **(filters or {})}
        # Over-fetch for the re-ranking stage.
        hits = await self._vectors.search(
            collection,
            query_vector,
            top_k=k * 3 if kb.rerank_enabled else k,
            score_threshold=kb.similarity_threshold,
            filters=combined_filters,
        )
        if kb.rerank_enabled and hits:
            hits = self._rerank(question, hits)[:k]
        else:
            hits = hits[:k]
        RAG_RETRIEVED_CHUNKS.observe(len(hits))
        return hits

    @staticmethod
    def _rerank(question: str, hits: list[VectorHit]) -> list[VectorHit]:
        """Lexical-overlap re-ranker blended with vector score (0.7 vec / 0.3 lex).

        Deterministic and dependency-free; a cross-encoder adapter can replace
        this without changing callers.
        """
        keywords = {t for t in re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}", question.lower())}

        def blended(hit: VectorHit) -> float:
            content = str(hit.payload.get("content", "")).lower()
            overlap = sum(1 for k in keywords if k in content) / (len(keywords) or 1)
            return 0.7 * hit.score + 0.3 * overlap

        return sorted(hits, key=blended, reverse=True)

    # -------------------------------------------------------------------- query
    async def query(
        self,
        kb: KnowledgeBaseModel,
        question: str,
        *,
        user_id: UUID | None = None,
        project_id: UUID | None = None,
        top_k: int | None = None,
        filters: dict | None = None,
    ) -> tuple[str, list[Citation], float, object]:
        """Full guarded RAG flow. Returns (answer, citations, confidence, gateway response)."""
        RAG_QUERIES.labels(str(kb.id)).inc()
        input_report = validate_input(question)  # raises GuardrailViolation on attack
        question_safe = input_report.redacted_text

        hits = await self.retrieve(kb, question_safe, top_k=top_k, filters=filters)
        if not hits:
            return (
                "I could not find relevant information in this knowledge base to answer "
                "your question.",
                [],
                0.0,
                None,
            )

        context_blocks = [
            f"[{i + 1}] ({hit.payload.get('filename')}, p.{hit.payload.get('page')}) "
            f"{hit.payload.get('content')}"
            for i, hit in enumerate(hits)
        ]
        request = ChatRequest(
            messages=[
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content=_RAG_SYSTEM_PROMPT.format(context="\n\n".join(context_blocks)),
                ),
                ChatMessage(role=MessageRole.USER, content=question_safe),
            ],
            model="",  # resolved by routing
            temperature=0.0,
        )
        route = self._gateway.resolve(provider=None, model=None)
        response = await self._gateway.chat(
            request, route, user_id=user_id, project_id=project_id, feature="rag"
        )

        output_report = validate_output(response.content)
        answer = output_report.redacted_text
        contexts = [str(h.payload.get("content", "")) for h in hits]
        confidence = groundedness_score(answer, contexts)

        citations = [
            Citation(
                document_id=UUID(hit.payload["document_id"]),
                filename=str(hit.payload.get("filename", "")),
                chunk_index=int(hit.payload.get("chunk_index", 0)),
                page=hit.payload.get("page"),
                score=round(hit.score, 4),
                excerpt=str(hit.payload.get("content", ""))[:300],
            )
            for hit in hits
        ]
        return answer, citations, confidence, response

    async def mark_failed(self, document: DocumentModel, error: str) -> None:
        document.status = DocumentStatus.FAILED.value
        document.error = error[:2000]
        DOCUMENTS_INDEXED.labels("failed").inc()
