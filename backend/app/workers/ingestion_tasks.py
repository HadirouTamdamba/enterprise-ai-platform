"""Async document ingestion task: parse → chunk → embed → index (idempotent)."""

import asyncio
from uuid import UUID

from app.ai.gateway.service import LLMGatewayService
from app.ai.rag.service import RAGService
from app.core.logging import configure_logging, get_logger
from app.domain.entities.ai import DocumentStatus
from app.infrastructure.database.repositories.ai import (
    DocumentRepository,
    KnowledgeBaseRepository,
)
from app.infrastructure.database.session import get_session_factory
from app.infrastructure.llm.registry import get_provider_registry
from app.infrastructure.observability.metrics import ACTIVE_INGESTIONS
from app.infrastructure.vector.qdrant_store import get_vector_store
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _ingest(document_id: str) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        documents = DocumentRepository(session)
        knowledge_bases = KnowledgeBaseRepository(session)
        document = await documents.get(UUID(document_id))
        kb = await knowledge_bases.get(document.knowledge_base_id)

        document.status = DocumentStatus.PROCESSING.value
        await session.commit()

        rag = RAGService(get_vector_store(), LLMGatewayService(get_provider_registry()))
        try:
            chunk_count = await rag.ingest_document(document, kb)
            document.status = DocumentStatus.INDEXED.value
            document.chunk_count = chunk_count
            document.error = ""
        except Exception as exc:
            logger.error("ingestion_failed", document=document_id, error=str(exc)[:500])
            document.status = DocumentStatus.FAILED.value
            document.error = str(exc)[:2000]
        await session.commit()
        return {"document_id": document_id, "status": document.status,
                "chunks": document.chunk_count}


@celery_app.task(name="ingestion.process_document", bind=True, max_retries=2)
def process_document(self, document_id: str) -> dict:
    """Celery entrypoint — bridges to the async ingestion pipeline."""
    configure_logging()
    ACTIVE_INGESTIONS.inc()
    try:
        return asyncio.run(_ingest(document_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        ACTIVE_INGESTIONS.dec()
