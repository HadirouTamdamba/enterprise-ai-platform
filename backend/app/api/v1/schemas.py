"""Pydantic request/response models for the v1 API (presentation layer only)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.entities.identity import Role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Errors ----------
class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}
    request_id: str = ""


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=10, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------- Users ----------
class UserResponse(ORMModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    organization_id: UUID | None
    created_at: datetime


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    organization_id: UUID | None = None


# ---------- Tenancy ----------
class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9-]{2,80}$")
    monthly_budget_usd: float = Field(default=0.0, ge=0)


class OrganizationResponse(ORMModel):
    id: UUID
    name: str
    slug: str
    monthly_budget_usd: float
    is_active: bool
    created_at: datetime


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = ""
    organization_id: UUID


class WorkspaceResponse(ORMModel):
    id: UUID
    name: str
    description: str
    organization_id: UUID
    created_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = ""
    workspace_id: UUID
    default_llm_provider: str | None = None
    default_llm_model: str | None = None
    monthly_budget_usd: float = Field(default=0.0, ge=0)


class ProjectResponse(ORMModel):
    id: UUID
    name: str
    description: str
    workspace_id: UUID
    default_llm_provider: str | None
    default_llm_model: str | None
    monthly_budget_usd: float
    is_active: bool
    created_at: datetime


# ---------- LLM Gateway ----------
class GatewayMessage(BaseModel):
    role: str = Field(pattern="^(system|user|assistant|tool)$")
    content: str


class ChatCompletionRequest(BaseModel):
    messages: list[GatewayMessage] = Field(min_length=1)
    provider: str | None = None
    model: str | None = None
    project_id: UUID | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=32768)
    response_schema: dict[str, Any] | None = None
    stream: bool = False


class UsageResponse(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    cached: bool = False


class ChatCompletionResponse(BaseModel):
    content: str
    provider: str
    model: str
    finish_reason: str
    usage: UsageResponse


# ---------- Prompts ----------
class PromptCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = ""
    project_id: UUID
    tags: list[str] = []
    template: str = Field(min_length=1)
    variables: list[str] = []
    model_hint: str = ""


class PromptVersionCreate(BaseModel):
    template: str = Field(min_length=1)
    variables: list[str] = []
    model_hint: str = ""
    changelog: str = ""
    activate: bool = True


class PromptVersionResponse(ORMModel):
    id: UUID
    prompt_id: UUID
    version: int
    template: str
    variables: list[str]
    model_hint: str
    changelog: str
    is_active: bool
    created_at: datetime


class PromptResponse(ORMModel):
    id: UUID
    name: str
    description: str
    tags: list[str]
    project_id: UUID
    created_at: datetime


# ---------- Knowledge bases & documents ----------
class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = ""
    project_id: UUID
    workspace_id: UUID
    chunking_strategy: str = "recursive"
    chunk_size: int = Field(default=800, ge=100, le=4000)
    chunk_overlap: int = Field(default=120, ge=0, le=1000)
    top_k: int = Field(default=8, ge=1, le=50)
    similarity_threshold: float = Field(default=0.35, ge=0, le=1)
    rerank_enabled: bool = True


class KnowledgeBaseResponse(ORMModel):
    id: UUID
    name: str
    description: str
    project_id: UUID
    workspace_id: UUID
    chunking_strategy: str
    chunk_size: int
    chunk_overlap: int
    embedding_provider: str
    embedding_model: str
    embedding_version: int
    top_k: int
    similarity_threshold: float
    rerank_enabled: bool
    created_at: datetime


class DocumentResponse(ORMModel):
    id: UUID
    knowledge_base_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    version: int
    status: str
    error: str
    chunk_count: int
    created_at: datetime


# ---------- RAG ----------
class CitationResponse(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int
    page: int | None
    score: float
    excerpt: str


class RAGQueryRequest(BaseModel):
    knowledge_base_id: UUID
    question: str = Field(min_length=3, max_length=8000)
    conversation_id: UUID | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    filters: dict[str, Any] | None = None


class RAGQueryResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    confidence: float
    conversation_id: UUID | None
    usage: UsageResponse


class FeedbackRequest(BaseModel):
    message_id: UUID
    rating: int = Field(ge=-1, le=1)
    comment: str = ""


# ---------- Agents ----------
class AgentRunRequest(BaseModel):
    agent: str
    task: str = Field(min_length=3, max_length=8000)
    project_id: UUID | None = None
    knowledge_base_id: UUID | None = None
    max_iterations: int = Field(default=6, ge=1, le=20)
    max_cost_usd: float = Field(default=1.0, gt=0, le=50)


class AgentStepResponse(BaseModel):
    iteration: int
    thought: str
    action: str
    result: str


class AgentRunResponse(BaseModel):
    agent: str
    output: str
    steps: list[AgentStepResponse]
    usage: UsageResponse


# ---------- Model registry / governance ----------
class ModelRegister(BaseModel):
    name: str
    version: str
    project_id: UUID
    model_type: str = "llm"
    risk_level: str = "minimal"
    metrics: dict[str, float] = {}
    training_dataset: str = ""
    artifact_uri: str = ""


class ModelResponse(ORMModel):
    id: UUID
    name: str
    version: str
    project_id: UUID
    model_type: str
    stage: str
    approval_status: str
    risk_level: str
    metrics: dict
    training_dataset: str
    artifact_uri: str
    rollback_version: str
    created_at: datetime


class ApprovalRequestCreate(BaseModel):
    resource_type: str
    resource_id: str
    justification: str = ""


class ApprovalDecision(BaseModel):
    approve: bool
    comment: str = ""


class ApprovalResponse(ORMModel):
    id: UUID
    resource_type: str
    resource_id: str
    requested_by: UUID
    reviewed_by: UUID | None
    status: str
    justification: str
    review_comment: str
    created_at: datetime


class AuditEventResponse(ORMModel):
    id: UUID
    created_at: datetime
    actor_id: UUID | None
    action: str
    resource_type: str
    resource_id: str
    details: dict
    entry_hash: str
