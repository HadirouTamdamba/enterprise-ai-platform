"""AI domain entities: prompts, knowledge bases, documents, conversations, usage,
model registry and governance artifacts. Pure Python — no framework imports."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class ChunkingStrategy(StrEnum):
    FIXED = "fixed"
    RECURSIVE = "recursive"
    SEMANTIC = "semantic"
    MARKDOWN = "markdown"


class RiskLevel(StrEnum):
    """EU AI Act inspired classification."""

    MINIMAL = "minimal"
    LIMITED = "limited"
    HIGH = "high"
    PROHIBITED = "prohibited"


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class DeploymentStrategy(StrEnum):
    DIRECT = "direct"
    SHADOW = "shadow"
    CANARY = "canary"


class ModelStage(StrEnum):
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


@dataclass(slots=True)
class Prompt:
    name: str
    project_id: UUID
    description: str = ""
    tags: list[str] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class PromptVersion:
    prompt_id: UUID
    version: int
    template: str
    variables: list[str] = field(default_factory=list)
    model_hint: str = ""
    changelog: str = ""
    is_active: bool = False
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def render(self, values: dict[str, str]) -> str:
        """Render the template; missing variables are a business rule violation."""
        missing = [v for v in self.variables if v not in values]
        if missing:
            raise ValueError(f"Missing prompt variables: {missing}")
        rendered = self.template
        for key, value in values.items():
            rendered = rendered.replace("{{" + key + "}}", value)
        return rendered


@dataclass(slots=True)
class KnowledgeBase:
    name: str
    project_id: UUID
    workspace_id: UUID
    description: str = ""
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE
    chunk_size: int = 800
    chunk_overlap: int = 120
    embedding_provider: str = ""
    embedding_model: str = ""
    embedding_version: int = 1
    top_k: int = 8
    similarity_threshold: float = 0.35
    rerank_enabled: bool = True
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Document:
    knowledge_base_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    storage_path: str
    version: int = 1
    status: DocumentStatus = DocumentStatus.UPLOADED
    error: str = ""
    chunk_count: int = 0
    metadata: dict = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Chunk:
    """A retrievable unit of knowledge with provenance."""

    document_id: UUID
    knowledge_base_id: UUID
    content: str
    index: int
    page: int | None = None
    document_version: int = 1
    metadata: dict = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Citation:
    document_id: UUID
    filename: str
    chunk_index: int
    page: int | None
    score: float
    excerpt: str


@dataclass(slots=True)
class UsageRecord:
    """One LLM call's accounting record — the atom of cost governance."""

    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: float
    user_id: UUID | None = None
    project_id: UUID | None = None
    feature: str = "gateway"  # gateway | rag | agent | evaluation | playground
    cached: bool = False
    success: bool = True
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(slots=True)
class RegisteredModel:
    name: str
    version: str
    project_id: UUID
    model_type: str  # llm | classifier | regressor | embedding | reranker
    stage: ModelStage = ModelStage.STAGING
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    risk_level: RiskLevel = RiskLevel.MINIMAL
    owner_id: UUID | None = None
    metrics: dict = field(default_factory=dict)
    training_dataset: str = ""
    artifact_uri: str = ""
    rollback_version: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def can_deploy_to_production(self) -> bool:
        """Business rule: high-risk models require explicit human approval."""
        if self.risk_level == RiskLevel.PROHIBITED:
            return False
        if self.risk_level == RiskLevel.HIGH:
            return self.approval_status == ApprovalStatus.APPROVED
        return self.approval_status in (ApprovalStatus.APPROVED, ApprovalStatus.PENDING_REVIEW)


@dataclass(slots=True)
class AuditEvent:
    """Append-only, hash-chained audit record."""

    actor_id: UUID | None
    action: str
    resource_type: str
    resource_id: str
    details: dict = field(default_factory=dict)
    previous_hash: str = ""
    entry_hash: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
