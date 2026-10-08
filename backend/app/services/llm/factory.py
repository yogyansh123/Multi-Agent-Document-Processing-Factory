"""
services/llm/factory.py
=======================
Factory for instantiating LLM providers.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.gemini import GeminiLLMProvider
from app.services.llm.ollama import OllamaLLMProvider
from app.services.llm.openai import OpenAILLMProvider


@lru_cache(maxsize=4)
def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """
    Return a cached singleton LLMProvider instance.

    If *provider_name* is None, uses ``settings.LLM_PROVIDER``.
    """
    name = (provider_name or settings.LLM_PROVIDER).lower()

    if name == "openai":
        return OpenAILLMProvider()
    elif name == "ollama":
        return OllamaLLMProvider()
    elif name == "gemini":
        return GeminiLLMProvider()
    elif name in {"anthropic", "google", "azure_openai"}:
        raise NotImplementedError(
            f"LLM provider '{name}' is planned for a future step and not yet implemented."
        )
    else:
        raise ValueError(f"Unknown LLM provider: '{name}'")
