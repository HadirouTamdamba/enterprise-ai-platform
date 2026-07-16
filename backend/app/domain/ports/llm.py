"""LLM provider port — the vendor-agnostic contract every adapter implements (ADR-002)."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(slots=True)
class ChatMessage:
    role: MessageRole
    content: str
    tool_call_id: str | None = None
    name: str | None = None


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ChatRequest:
    messages: list[ChatMessage]
    model: str
    temperature: float = 0.2
    max_tokens: int = 2048
    tools: list[ToolSpec] = field(default_factory=list)
    response_schema: dict[str, Any] | None = None  # structured output (JSON Schema)
    stop: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class UsageInfo:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(slots=True)
class ChatResponse:
    content: str
    model: str
    provider: str
    usage: UsageInfo = field(default_factory=UsageInfo)
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    cached: bool = False


@dataclass(slots=True)
class StreamChunk:
    delta: str
    finish_reason: str | None = None
    usage: UsageInfo | None = None


class LLMProviderPort(ABC):
    """Every LLM vendor adapter implements this contract."""

    name: str = "abstract"

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Execute a chat completion."""

    @abstractmethod
    def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion."""

    @abstractmethod
    def available(self) -> bool:
        """Whether the adapter is configured (e.g., API key present)."""


class EmbeddingProviderPort(ABC):
    """Contract for embedding vendors."""

    name: str = "abstract"

    @abstractmethod
    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Embed a batch of texts."""

    @abstractmethod
    def available(self) -> bool: ...
