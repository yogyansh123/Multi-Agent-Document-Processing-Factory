"""
services/llm/ollama.py
======================
Concrete LLM provider using Ollama's native structured outputs API (/api/chat).
"""

from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm.base import (
    LLMAPIError,
    LLMConfigurationError,
    LLMError,
    LLMProvider,
)

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class OllamaLLMProvider(LLMProvider):
    """
    Ollama-based LLM provider leveraging native JSON schema constrained generation.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 300.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        raw_url = base_url if base_url is not None else settings.OLLAMA_BASE_URL
        if not raw_url:
            raise LLMConfigurationError(
                "OLLAMA_BASE_URL is not configured. Please set OLLAMA_BASE_URL in environment or .env.",
                provider=self.provider_name,
            )
        self._base_url = raw_url.rstrip("/")
        self._model = model or settings.OLLAMA_MODEL
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = client

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    async def aclose(self) -> None:
        """Close the underlying HTTP client if open."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        """
        Generate structured output adhering to *schema* using Ollama's /api/chat endpoint.
        """
        client = self._get_client()

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        schema_json = schema.model_json_schema()

        payload = {
            "model": self._model,
            "messages": messages,
            "format": schema_json,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        try:
            logger.info(
                "llm.ollama.request",
                model=self._model,
                schema=schema.__name__,
                temperature=temperature,
                endpoint=f"{self._base_url}/api/chat",
            )
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise LLMAPIError(
                f"Failed to connect to Ollama at {self._base_url}: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
        except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            raise LLMAPIError(
                f"Ollama request timed out after {self._timeout}s: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMAPIError(
                f"Ollama API returned HTTP {exc.response.status_code}: {exc.response.text}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMAPIError(
                f"Ollama network request failed: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
        except Exception as exc:
            raise LLMError(
                f"Unexpected error communicating with Ollama: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc

        try:
            data = response.json()
        except Exception as exc:
            raise LLMAPIError(
                f"Ollama returned non-JSON HTTP response body: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc

        message = data.get("message")
        if not message or not isinstance(message, dict):
            raise LLMAPIError(
                f"Ollama response missing 'message' object: {data}",
                provider=self.provider_name,
            )

        content = message.get("content")
        if not content or not isinstance(content, str):
            raise LLMAPIError(
                "Ollama returned empty or invalid response content in message",
                provider=self.provider_name,
            )

        try:
            return schema.model_validate_json(content)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.error(
                "llm.ollama.validation_error",
                schema=schema.__name__,
                content=content[:500],
                error=str(exc),
            )
            raise LLMAPIError(
                f"Failed to parse or validate Ollama output against {schema.__name__}: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
