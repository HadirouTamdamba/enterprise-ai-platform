"""LLM provider adapters implementing LLMProviderPort (ADR-002).

All adapters use httpx directly — no vendor SDK lock-in, uniform timeout/retry
behavior, and a single dependency surface. Each adapter normalizes its vendor's
wire format to the canonical ChatRequest/ChatResponse contract.
"""

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import ModelInferenceError, ProviderUnavailableError
from app.domain.ports.llm import (
    ChatRequest,
    ChatResponse,
    LLMProviderPort,
    MessageRole,
    StreamChunk,
    ToolCall,
    UsageInfo,
)

_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


class AnthropicProvider(LLMProviderPort):
    """Anthropic Messages API."""

    name = "anthropic"

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def available(self) -> bool:
        return bool(self._api_key)

    def _payload(self, request: ChatRequest) -> dict[str, Any]:
        system = "\n".join(
            m.content for m in request.messages if m.role == MessageRole.SYSTEM
        )
        messages = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
            if m.role in (MessageRole.USER, MessageRole.ASSISTANT)
        ]
        payload: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        if request.stop:
            payload["stop_sequences"] = request.stop
        if request.tools:
            payload["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in request.tools
            ]
        return payload

    async def chat(self, request: ChatRequest) -> ChatResponse:
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{self._base_url}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=self._payload(request),
            )
        _raise_for_status(response, self.name)
        data = response.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b["type"] == "text")
        tool_calls = [
            ToolCall(id=b["id"], name=b["name"], arguments=b.get("input", {}))
            for b in data.get("content", [])
            if b["type"] == "tool_use"
        ]
        usage = data.get("usage", {})
        return ChatResponse(
            content=text,
            model=data.get("model", request.model),
            provider=self.name,
            usage=UsageInfo(
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
            ),
            tool_calls=tool_calls,
            finish_reason=data.get("stop_reason", "stop") or "stop",
            latency_ms=(time.perf_counter() - start) * 1000,
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        payload = self._payload(request) | {"stream": True}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            ) as response:
                _raise_for_status(response, self.name)
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    if event.get("type") == "content_block_delta":
                        yield StreamChunk(delta=event["delta"].get("text", ""))
                    elif event.get("type") == "message_stop":
                        yield StreamChunk(delta="", finish_reason="stop")


class OpenAICompatibleProvider(LLMProviderPort):
    """OpenAI Chat Completions wire format.

    Covers OpenAI, Mistral, DeepSeek, OpenRouter, Ollama, Azure OpenAI and any
    OpenAI-compatible endpoint — the de-facto industry standard.
    """

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        extra_headers: dict[str, str] | None = None,
        requires_key: bool = True,
    ) -> None:
        self.name = name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._extra_headers = extra_headers or {}
        self._requires_key = requires_key

    def available(self) -> bool:
        return bool(self._api_key) or not self._requires_key

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json", **self._extra_headers}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"
        return headers

    def _payload(self, request: ChatRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
        }
        if request.stop:
            payload["stop"] = request.stop
        if request.response_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": request.response_schema},
            }
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]
        return payload

    async def chat(self, request: ChatRequest) -> ChatResponse:
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(request),
            )
        _raise_for_status(response, self.name)
        data = response.json()
        choice = data["choices"][0]
        message = choice.get("message", {})
        tool_calls = [
            ToolCall(
                id=tc.get("id", ""),
                name=tc["function"]["name"],
                arguments=json.loads(tc["function"].get("arguments") or "{}"),
            )
            for tc in message.get("tool_calls") or []
        ]
        usage = data.get("usage") or {}
        return ChatResponse(
            content=message.get("content") or "",
            model=data.get("model", request.model),
            provider=self.name,
            usage=UsageInfo(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            ),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop") or "stop",
            latency_ms=(time.perf_counter() - start) * 1000,
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        payload = self._payload(request) | {"stream": True}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                _raise_for_status(response, self.name)
                async for line in response.aiter_lines():
                    if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                        continue
                    event = json.loads(line[6:])
                    delta = event["choices"][0].get("delta", {}).get("content", "")
                    finish = event["choices"][0].get("finish_reason")
                    yield StreamChunk(delta=delta or "", finish_reason=finish)


class GeminiProvider(LLMProviderPort):
    """Google Gemini generateContent API."""

    name = "gemini"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"

    def available(self) -> bool:
        return bool(self._api_key)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        start = time.perf_counter()
        system = "\n".join(m.content for m in request.messages if m.role == MessageRole.SYSTEM)
        contents = [
            {
                "role": "user" if m.role == MessageRole.USER else "model",
                "parts": [{"text": m.content}],
            }
            for m in request.messages
            if m.role in (MessageRole.USER, MessageRole.ASSISTANT)
        ]
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{self._base_url}/models/{request.model}:generateContent",
                params={"key": self._api_key},
                json=payload,
            )
        _raise_for_status(response, self.name)
        data = response.json()
        candidate = (data.get("candidates") or [{}])[0]
        parts = candidate.get("content", {}).get("parts", [])
        usage = data.get("usageMetadata", {})
        return ChatResponse(
            content="".join(p.get("text", "") for p in parts),
            model=request.model,
            provider=self.name,
            usage=UsageInfo(
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
            ),
            finish_reason=candidate.get("finishReason", "stop").lower(),
            latency_ms=(time.perf_counter() - start) * 1000,
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        # Gemini streaming uses a different SSE shape; v1 falls back to buffered delivery.
        response = await self.chat(request)
        yield StreamChunk(delta=response.content, finish_reason="stop", usage=response.usage)


class FakeProvider(LLMProviderPort):
    """Deterministic provider for tests and keyless demo mode."""

    name = "fake"

    def __init__(self, canned: str = "This is a deterministic response for testing.") -> None:
        self._canned = canned
        self.calls: list[ChatRequest] = []

    def available(self) -> bool:
        return True

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.calls.append(request)
        prompt_tokens = sum(len(m.content.split()) for m in request.messages)
        return ChatResponse(
            content=self._canned,
            model=request.model,
            provider=self.name,
            usage=UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=len(self._canned.split())),
            latency_ms=1.0,
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        for word in self._canned.split():
            yield StreamChunk(delta=word + " ")
        yield StreamChunk(delta="", finish_reason="stop")


def _raise_for_status(response: httpx.Response, provider: str) -> None:
    if response.status_code in (429, 500, 502, 503, 504):
        raise ProviderUnavailableError(
            f"Provider '{provider}' unavailable (HTTP {response.status_code})"
        )
    if response.status_code >= 400:
        raise ModelInferenceError(
            f"Provider '{provider}' rejected the request (HTTP {response.status_code})",
            details={"provider": provider, "status": response.status_code},
        )
