"""
services/llm/openai.py
======================
Concrete LLM provider using OpenAI's Structured Outputs API.
"""

from __future__ import annotations

from typing import TypeVar

import openai
from openai import APIError, AuthenticationError, RateLimitError
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm.base import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMProvider,
)

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class OpenAILLMProvider(LLMProvider):
    """
    OpenAI-based LLM provider leveraging native structured outputs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model = model or settings.OPENAI_MODEL
        self._client: openai.AsyncOpenAI | None = None

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_client(self) -> openai.AsyncOpenAI:
        if not self._api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY is not configured. Please set OPENAI_API_KEY in environment or .env.",
                provider=self.provider_name,
            )
        if self._client is None:
            self._client = openai.AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        """
        Generate structured output adhering to *schema* using OpenAI parse API.
        """
        client = self._get_client()

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            logger.info(
                "llm.openai.request",
                model=self._model,
                schema=schema.__name__,
                temperature=temperature,
            )
            completion = await client.beta.chat.completions.parse(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                response_format=schema,
                temperature=temperature,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                refusal = completion.choices[0].message.refusal
                raise LLMAPIError(
                    f"Model refused or returned empty structured output: {refusal}",
                    provider=self.provider_name,
                )
            return parsed
        except AuthenticationError as exc:
            raise LLMAuthenticationError(
                f"OpenAI authentication failed: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
        except RateLimitError as exc:
            raise LLMAPIError(
                f"OpenAI rate limit exceeded: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
        except APIError as exc:
            raise LLMAPIError(
                f"OpenAI API error: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(
                f"LLM generation failed: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
