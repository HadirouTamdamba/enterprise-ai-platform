"""RAG Studio endpoints (F-20..F-29): knowledge bases, documents, queries, feedback."""

import uuid as uuidlib
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, UploadFile

from app.ai.gateway.pricing import get_pricing
from app.ai.gateway.service import LLMGatewayService
from app.ai.rag.service import RAGService
from app.api.deps import AppSettings, CurrentUser, DbSession, require_role
from app.api.v1.schemas import (
    CitationResponse,
    DocumentResponse,
    FeedbackRequest,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    UsageResponse,
)
from app.core.exceptions import ConflictError, ValidationError
from app.domain.entities.identity import Role
from app.domain.services.routing import estimate_cost_usd
from app.infrastructure.database.models import (
    ConversationModel,
    DocumentModel,
    KnowledgeBaseModel,
    MessageModel,
)
from app.infrastructure.database.repositories.ai import (
    AuditRepository,
    ConversationRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
    MessageRepository,
    UsageRepository,
)
from app.infrastructure.ingestion.parsers import SUPPORTED_EXTENSIONS
from app.infrastructure.llm.registry import get_provider_registry
from app.infrastructure.vector.qdrant_store import get_vector_store

router = APIRouter(prefix="/rag", tags=["rag"])


def _rag_service(session) -> RAGService:
    gateway = LLMGatewayService(get_provider_registry(), UsageRepository(session))
    return RAGService(get_vector_store(), gateway)


# ------------------------------------------------------------ knowledge bases
@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse, status_code=201,
             dependencies=[require_role(Role.ENGINEER)])
async def create_knowledge_base(
    body: KnowledgeBaseCreate, session: DbSession, actor: CurrentUser, settings: AppSettings
) -> KnowledgeBaseResponse:
    repo = KnowledgeBaseRepository(session)
    if await repo.list(project_id=body.project_id, name=body.name):
        raise ConflictError(f"Knowledge base '{body.name}' already exists in this project")
    kb = await repo.add(
        KnowledgeBaseModel(
            **body.model_dump(),
            embedding_provider=settings.default_embedding_provider,
            embedding_model=settings.default_embedding_model,
        )
    )
    await AuditRepository(session).append(
        actor_id=actor.id, action="knowledge_base.created", resource_type="knowledge_base",
        resource_id=str(kb.id),
    )
    return KnowledgeBaseResponse.model_validate(kb)


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseResponse],
            dependencies=[require_role(Role.VIEWER)])
async def list_knowledge_bases(
    session: DbSession, project_id: UUID | None = None
) -> list[KnowledgeBaseResponse]:
    items = await KnowledgeBaseRepository(session).list(project_id=project_id)
    return [KnowledgeBaseResponse.model_validate(kb) for kb in items]


# ----------------------------------------------------------------- documents
@router.post("/knowledge-bases/{kb_id}/documents", response_model=DocumentResponse,
             status_code=202, dependencies=[require_role(Role.ENGINEER)])
async def upload_document(
    kb_id: UUID,
    file: UploadFile,
    session: DbSession,
    actor: CurrentUser,
    settings: AppSettings,
) -> DocumentResponse:
    """Secure upload → async ingestion via Celery (202 Accepted)."""
    kb = await KnowledgeBaseRepository(session).get(kb_id)
    filename = Path(file.filename or "upload").name  # strip any path components
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValidationError(f"Unsupported file type '{extension}'")

    upload_dir = Path(settings.upload_dir) / str(kb.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_path = upload_dir / f"{uuidlib.uuid4().hex}{extension}"

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    size = 0
    with storage_path.open("wb") as target:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                target.close()
                storage_path.unlink(missing_ok=True)
                raise ValidationError(f"File exceeds {settings.max_upload_size_mb} MB limit")
            target.write(chunk)

    documents = DocumentRepository(session)
    previous = await documents.find_by_filename(kb_id, filename)
    document = await documents.add(
        DocumentModel(
            knowledge_base_id=kb_id,
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=size,
            storage_path=str(storage_path),
            version=(previous.version + 1) if previous else 1,
        )
    )
    await AuditRepository(session).append(
        actor_id=actor.id, action="document.uploaded", resource_type="document",
        resource_id=str(document.id), details={"filename": filename, "version": document.version},
    )
    await session.commit()

    if settings.environment == "test":
        # Synchronous ingestion in tests — no broker available.
        rag = _rag_service(session)
        try:
            document.chunk_count = await rag.ingest_document(document, kb)
            document.status = "indexed"
        except Exception as exc:
            document.status = "failed"
            document.error = str(exc)[:2000]
    else:
        from app.workers.ingestion_tasks import process_document

        process_document.delay(str(document.id))

    return DocumentResponse.model_validate(document)


@router.get("/knowledge-bases/{kb_id}/documents", response_model=list[DocumentResponse],
            dependencies=[require_role(Role.VIEWER)])
async def list_documents(kb_id: UUID, session: DbSession) -> list[DocumentResponse]:
    items = await DocumentRepository(session).list(knowledge_base_id=kb_id, limit=200)
    return [DocumentResponse.model_validate(d) for d in items]


# --------------------------------------------------------------------- query
@router.post("/query", response_model=RAGQueryResponse,
             dependencies=[require_role(Role.VIEWER)])
async def rag_query(
    body: RAGQueryRequest, session: DbSession, user: CurrentUser
) -> RAGQueryResponse:
    kb = await KnowledgeBaseRepository(session).get(body.knowledge_base_id)
    rag = _rag_service(session)
    answer, citations, confidence, response = await rag.query(
        kb, body.question, user_id=user.id, project_id=kb.project_id,
        top_k=body.top_k, filters=body.filters,
    )

    conversations = ConversationRepository(session)
    if body.conversation_id:
        conversation = await conversations.get(body.conversation_id)
    else:
        conversation = await conversations.add(
            ConversationModel(user_id=user.id, project_id=kb.project_id,
                              title=body.question[:120])
        )
    citation_dicts = [
        {"document_id": str(c.document_id), "filename": c.filename,
         "chunk_index": c.chunk_index, "page": c.page, "score": c.score,
         "excerpt": c.excerpt}
        for c in citations
    ]
    usage_dict = {}
    cost = 0.0
    if response is not None:
        cost = estimate_cost_usd(
            response.usage.prompt_tokens, response.usage.completion_tokens,
            get_pricing(), response.model,
        )
        usage_dict = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "cost_usd": cost, "latency_ms": response.latency_ms,
        }
    session.add(MessageModel(conversation_id=conversation.id, role="user",
                             content=body.question))
    answer_message = MessageModel(
        conversation_id=conversation.id, role="assistant", content=answer,
        citations=citation_dicts, usage=usage_dict,
    )
    session.add(answer_message)
    await session.flush()

    return RAGQueryResponse(
        answer=answer,
        citations=[CitationResponse(**c) for c in citation_dicts],
        confidence=confidence,
        conversation_id=conversation.id,
        usage=UsageResponse(
            prompt_tokens=usage_dict.get("prompt_tokens", 0),
            completion_tokens=usage_dict.get("completion_tokens", 0),
            total_tokens=usage_dict.get("prompt_tokens", 0)
            + usage_dict.get("completion_tokens", 0),
            cost_usd=cost,
            latency_ms=round(usage_dict.get("latency_ms", 0.0), 2),
        ),
    )


# ------------------------------------------------------------------ feedback
@router.post("/feedback", status_code=204, dependencies=[require_role(Role.VIEWER)])
async def submit_feedback(
    body: FeedbackRequest, session: DbSession, actor: CurrentUser
) -> None:
    """Feedback loop (F-28): ratings feed future evaluation datasets."""
    message = await MessageRepository(session).get(body.message_id)
    message.feedback = body.rating
    message.feedback_comment = body.comment[:2000]
    await AuditRepository(session).append(
        actor_id=actor.id, action="rag.feedback", resource_type="message",
        resource_id=str(body.message_id), details={"rating": body.rating},
    )
