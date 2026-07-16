"""Repositories for AI aggregates: prompts, knowledge bases, documents, conversations,
usage records, model registry, governance."""

import hashlib
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, func, select

from app.infrastructure.database.models import (
    ApprovalModel,
    AuditEventModel,
    ConversationModel,
    DocumentModel,
    KnowledgeBaseModel,
    MessageModel,
    PromptModel,
    PromptVersionModel,
    RegisteredModelModel,
    RiskRegisterModel,
    UsageRecordModel,
)
from app.infrastructure.database.repositories.base import BaseRepository


class PromptRepository(BaseRepository[PromptModel]):
    model = PromptModel

    async def latest_version(self, prompt_id: UUID) -> PromptVersionModel | None:
        result = await self.session.execute(
            select(PromptVersionModel)
            .where(PromptVersionModel.prompt_id == prompt_id)
            .order_by(desc(PromptVersionModel.version))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def active_version(self, prompt_id: UUID) -> PromptVersionModel | None:
        result = await self.session.execute(
            select(PromptVersionModel).where(
                PromptVersionModel.prompt_id == prompt_id,
                PromptVersionModel.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def versions(self, prompt_id: UUID) -> list[PromptVersionModel]:
        result = await self.session.execute(
            select(PromptVersionModel)
            .where(PromptVersionModel.prompt_id == prompt_id)
            .order_by(PromptVersionModel.version)
        )
        return list(result.scalars().all())

    async def deactivate_versions(self, prompt_id: UUID) -> None:
        for version in await self.versions(prompt_id):
            version.is_active = False
        await self.session.flush()


class KnowledgeBaseRepository(BaseRepository[KnowledgeBaseModel]):
    model = KnowledgeBaseModel


class DocumentRepository(BaseRepository[DocumentModel]):
    model = DocumentModel

    async def find_by_filename(
        self, knowledge_base_id: UUID, filename: str
    ) -> DocumentModel | None:
        result = await self.session.execute(
            select(DocumentModel)
            .where(
                DocumentModel.knowledge_base_id == knowledge_base_id,
                DocumentModel.filename == filename,
            )
            .order_by(desc(DocumentModel.version))
            .limit(1)
        )
        return result.scalar_one_or_none()


class ConversationRepository(BaseRepository[ConversationModel]):
    model = ConversationModel

    async def messages(self, conversation_id: UUID, limit: int = 50) -> list[MessageModel]:
        result = await self.session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())


class MessageRepository(BaseRepository[MessageModel]):
    model = MessageModel


class UsageRepository(BaseRepository[UsageRecordModel]):
    model = UsageRecordModel

    async def totals(
        self,
        *,
        project_id: UUID | None = None,
        since: datetime | None = None,
    ) -> dict:
        stmt = select(
            func.count(UsageRecordModel.id),
            func.coalesce(func.sum(UsageRecordModel.prompt_tokens), 0),
            func.coalesce(func.sum(UsageRecordModel.completion_tokens), 0),
            func.coalesce(func.sum(UsageRecordModel.cost_usd), 0.0),
            func.coalesce(func.avg(UsageRecordModel.latency_ms), 0.0),
        )
        if project_id is not None:
            stmt = stmt.where(UsageRecordModel.project_id == project_id)
        if since is not None:
            stmt = stmt.where(UsageRecordModel.created_at >= since)
        row = (await self.session.execute(stmt)).one()
        return {
            "requests": int(row[0]),
            "prompt_tokens": int(row[1]),
            "completion_tokens": int(row[2]),
            "cost_usd": round(float(row[3]), 6),
            "avg_latency_ms": round(float(row[4]), 2),
        }

    async def by_model(self, since: datetime | None = None) -> list[dict]:
        stmt = select(
            UsageRecordModel.provider,
            UsageRecordModel.model,
            func.count(UsageRecordModel.id),
            func.coalesce(func.sum(UsageRecordModel.cost_usd), 0.0),
        ).group_by(UsageRecordModel.provider, UsageRecordModel.model)
        if since is not None:
            stmt = stmt.where(UsageRecordModel.created_at >= since)
        rows = (await self.session.execute(stmt)).all()
        return [
            {"provider": r[0], "model": r[1], "requests": int(r[2]), "cost_usd": round(float(r[3]), 6)}
            for r in rows
        ]


class ModelRegistryRepository(BaseRepository[RegisteredModelModel]):
    model = RegisteredModelModel


class ApprovalRepository(BaseRepository[ApprovalModel]):
    model = ApprovalModel


class RiskRegisterRepository(BaseRepository[RiskRegisterModel]):
    model = RiskRegisterModel


class AuditRepository(BaseRepository[AuditEventModel]):
    model = AuditEventModel

    async def append(
        self,
        *,
        actor_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: str = "",
        details: dict | None = None,
    ) -> AuditEventModel:
        """Append a hash-chained audit event (tamper-evident)."""
        last = await self.session.execute(
            select(AuditEventModel.entry_hash)
            .order_by(desc(AuditEventModel.created_at))
            .limit(1)
        )
        previous_hash = last.scalar_one_or_none() or ""
        payload = json.dumps(
            {
                "actor": str(actor_id) if actor_id else None,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": details or {},
                "previous": previous_hash,
            },
            sort_keys=True,
            default=str,
        )
        entry_hash = hashlib.sha256(payload.encode()).hexdigest()
        event = AuditEventModel(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        return await self.add(event)
