"""Async document ingestion task: parse → chunk → embed → index (idempotent).

Celery is synchronous; the ingestion pipeline is async. Rather than a fresh
``asyncio.run()`` per task — which closes the loop and orphans loop-bound
singletons (the async SQLAlchemy engine, the AsyncQdrantClient), causing
``Event loop is closed`` on every task after the first — each worker process
keeps ONE persistent event loop for its whole lifetime. All async resources
bind to it once and stay valid across tasks.
"""

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

_loop: asyncio.AbstractEventLoop | None = None


def _get_loop() -> asyncio.AbstractEventLoop:
    """Return this worker process's persistent event loop, creating it once."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


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
    """Celery entrypoint — runs the async pipeline on the persistent loop."""
    configure_logging()
    ACTIVE_INGESTIONS.inc()
    try:
        return _get_loop().run_until_complete(_ingest(document_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        ACTIVE_INGESTIONS.dec()
