"""Provider registry — builds every configured adapter from settings.

Adding a provider = one entry here + config. Business logic never imports adapters.
"""

from functools import lru_cache

from app.core.config import get_settings
from app.core.exceptions import ProviderUnavailableError
from app.domain.ports.llm import LLMProviderPort
from app.infrastructure.llm.providers import (
    AnthropicProvider,
    FakeProvider,
    GeminiProvider,
    OpenAICompatibleProvider,
)


class ProviderRegistry:
    def __init__(self, providers: dict[str, LLMProviderPort]) -> None:
        self._providers = providers

    def get(self, name: str) -> LLMProviderPort:
        provider = self._providers.get(name)
        if provider is None:
            raise ProviderUnavailableError(f"Unknown provider '{name}'")
        if not provider.available():
            raise ProviderUnavailableError(f"Provider '{name}' is not configured")
        return provider

    def configured(self) -> list[str]:
        return [name for name, p in self._providers.items() if p.available()]

    def register(self, provider: LLMProviderPort) -> None:
        self._providers[provider.name] = provider


@lru_cache
def get_provider_registry() -> ProviderRegistry:
    s = get_settings()
    providers: dict[str, LLMProviderPort] = {
        "anthropic": AnthropicProvider(s.anthropic_api_key),
        "openai": OpenAICompatibleProvider(
            "openai", s.openai_api_key, "https://api.openai.com/v1"
        ),
        "mistral": OpenAICompatibleProvider(
            "mistral", s.mistral_api_key, "https://api.mistral.ai/v1"
        ),
        "deepseek": OpenAICompatibleProvider(
            "deepseek", s.deepseek_api_key, "https://api.deepseek.com/v1"
        ),
        "openrouter": OpenAICompatibleProvider(
            "openrouter", s.openrouter_api_key, "https://openrouter.ai/api/v1"
        ),
        # Llama models are served via OpenRouter/Bedrock/Ollama endpoints.
        "ollama": OpenAICompatibleProvider(
            "ollama", "", f"{s.ollama_base_url}/v1", requires_key=False
        ),
        "gemini": GeminiProvider(s.google_api_key),
        "azure_openai": OpenAICompatibleProvider(
            "azure_openai",
            s.azure_openai_api_key,
            f"{s.azure_openai_endpoint.rstrip('/')}/openai/deployments" if s.azure_openai_endpoint else "",
            extra_headers={"api-key": s.azure_openai_api_key} if s.azure_openai_api_key else None,
        ),
        # Bedrock & Vertex expose OpenAI-compatible endpoints via their gateways;
        # native SigV4/OAuth adapters plug in here without touching business logic.
        "bedrock": OpenAICompatibleProvider(
            "bedrock",
            s.aws_secret_access_key,
            f"https://bedrock-runtime.{s.aws_region}.amazonaws.com/openai/v1",
        ),
        "vertex": OpenAICompatibleProvider(
            "vertex",
            s.google_api_key,
            f"https://aiplatform.googleapis.com/v1/projects/{s.vertex_project_id}/locations/global/endpoints/openapi"
            if s.vertex_project_id
            else "",
        ),
    }
    if s.environment == "test":
        providers["fake"] = FakeProvider()
    return ProviderRegistry(providers)
