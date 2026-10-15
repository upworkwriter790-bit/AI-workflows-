from __future__ import annotations

from app.core.config import Settings
from app.services.ai.base import AIProvider
from app.services.ai.mock import MockAIProvider


def get_ai_provider(settings: Settings) -> AIProvider | None:
    """Returns None (not an error) when AI editing is disabled or no key
    is configured — callers must disable the AI panel/endpoints
    gracefully in that case, never fall back to a hallucinated response.
    """
    if not settings.ai_edit_enabled:
        return None
    if not settings.ai_api_key:
        return None
    if settings.ai_provider == "anthropic":
        from app.services.ai.anthropic_provider import AnthropicAIProvider

        return AnthropicAIProvider(api_key=settings.ai_api_key, model=settings.ai_model)
    if settings.ai_provider == "mock":
        return MockAIProvider()
    raise NotImplementedError(f"AI_PROVIDER={settings.ai_provider!r} has no adapter yet")
