"""
services/llm
============
LLM abstraction layer for the Multi-Agent Document Processing Factory.
"""

from app.services.llm.base import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMProvider,
)
from app.services.llm.factory import get_llm_provider
from app.services.llm.openai import OpenAILLMProvider

__all__ = [
    "LLMAPIError",
    "LLMAuthenticationError",
    "LLMConfigurationError",
    "LLMError",
    "LLMProvider",
    "OpenAILLMProvider",
    "get_llm_provider",
]
