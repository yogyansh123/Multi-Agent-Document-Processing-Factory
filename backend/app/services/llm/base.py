"""
services/llm/base.py
====================
Abstract interface for Large Language Model (LLM) providers.

All concrete LLM backends (OpenAI, Anthropic, Google, Ollama, etc.) must implement
``LLMProvider``. The agents and application layer only import ``LLMProvider`` —
never concrete SDK classes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base exception for all LLM errors."""

    def __init__(self, message: str, provider: str, cause: Exception | None = None) -> None:
        self.provider = provider
        self.cause = cause
        super().__init__(message)


class LLMConfigurationError(LLMError):
    """Raised when an LLM provider is misconfigured (e.g. missing API key)."""


class LLMAuthenticationError(LLMError):
    """Raised when provider authentication fails (e.g. invalid API key)."""


class LLMAPIError(LLMError):
    """Raised when the LLM provider returns an API error or rate limit."""


class LLMProvider(ABC):
    """
    Abstract interface for LLM operations.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Lowercase identifier for the provider (e.g. 'openai')."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        """
        Generate a structured response adhering to a Pydantic schema.

        Parameters
        ----------
        prompt:
            User prompt / document content to process.
        schema:
            Pydantic model class defining the expected output structure.
        system_prompt:
            Optional instructions defining model behavior.
        temperature:
            Sampling temperature (0.0 for deterministic classification).

        Returns
        -------
        An instance of schema (T) parsed from the model output.

        Raises
        ------
        LLMError: If invocation or schema validation fails.
        """
