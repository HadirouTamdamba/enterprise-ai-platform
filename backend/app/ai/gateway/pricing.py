"""Model pricing table — configuration, not code logic.

USD per 1M tokens: model -> (input, output). Loaded from an optional JSON override
file so operators can update prices without a release.
"""

import json
from pathlib import Path

_DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-4-8": (15.0, 75.0),
    "claude-haiku-4-5-20251001": (0.8, 4.0),
    # OpenAI
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    # Google
    "gemini-2.0-flash": (0.1, 0.4),
    "gemini-1.5-pro": (1.25, 5.0),
    # Mistral
    "mistral-large-latest": (2.0, 6.0),
    "mistral-small-latest": (0.2, 0.6),
    # DeepSeek
    "deepseek-chat": (0.27, 1.1),
    # Embeddings
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}

_OVERRIDE_FILE = Path(__file__).parent / "pricing_override.json"


def get_pricing() -> dict[str, tuple[float, float]]:
    pricing = dict(_DEFAULT_PRICING)
    if _OVERRIDE_FILE.exists():
        overrides = json.loads(_OVERRIDE_FILE.read_text())
        pricing.update({model: tuple(rates) for model, rates in overrides.items()})
    return pricing
