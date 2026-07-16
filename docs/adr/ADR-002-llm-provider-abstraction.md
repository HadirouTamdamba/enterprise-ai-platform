# ADR-002: Port/adapter abstraction for LLM providers

**Status:** Accepted · **Date:** 2026-07-16

## Context
The platform must support 11 providers (Claude, GPT, Gemini, Mistral, Llama, DeepSeek, Ollama,
OpenRouter, Azure OpenAI, Bedrock, Vertex) and enterprise customers must never be locked to one
vendor. SDKs differ in auth, streaming, tool calling and usage reporting.

## Decision
Define a domain port `LLMProviderPort` with a canonical `ChatRequest/ChatResponse/UsageInfo`
contract. Each provider is an infrastructure adapter registered in a provider registry keyed by
name. Model names, pricing and fallback chains live in configuration. Business logic only sees the
port; the gateway service applies routing policy, retries, fallback, caching and accounting.

## Consequences
+ Adding a provider = one adapter file + config entry; zero business-logic change.
+ Deterministic tests via a `FakeLLMProvider` adapter.
− Lowest-common-denominator features must be normalized (e.g., tool-call formats) in adapters.
