"""
services/llm/gemini.py
======================
Concrete LLM provider using Google Gemini's REST API with Structured Outputs.
Supports Google AI Studio Free Tier models (e.g. gemini-3.5-flash-lite).
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

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


def _clean_schema_for_gemini(schema_cls: type[BaseModel]) -> dict[str, Any]:
    """
    Generate and clean a JSON schema for Gemini's responseSchema parameter.
    Inlines all $defs so the schema is self-contained without unresolved $ref pointers,
    and strips metadata keys unsupported by Gemini.
    """
    raw_schema = schema_cls.model_json_schema()
    defs = raw_schema.pop("$defs", {})

    def _resolve(item: Any) -> Any:
        if isinstance(item, dict):
            if "$ref" in item:
                ref_key = item["$ref"].split("/")[-1]
                if ref_key in defs:
                    resolved = _resolve(defs[ref_key])
                    merged = {**resolved, **{k: v for k, v in item.items() if k != "$ref"}}
                    return _sanitize(merged)
            return _sanitize({k: _resolve(v) for k, v in item.items()})
        elif isinstance(item, list):
            return [_resolve(x) for x in item]
        return item

    def _sanitize(d: Any) -> Any:
        if not isinstance(d, dict):
            return d
        for key in ("$schema", "title", "default"):
            d.pop(key, None)
        return d

    return _resolve(raw_schema)


class GeminiLLMProvider(LLMProvider):
    """
    Google Gemini LLM provider using the official Generative Language REST API.
    Compatible with Google AI Studio Free Tier projects.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://generativelanguage.googleapis.com",
    ) -> None:
        self._api_key = api_key or settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
        self._model = model or settings.GEMINI_MODEL or "gemini-3.5-flash-lite"
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = client
        self._base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _get_client(self) -> httpx.AsyncClient:
        if not self._api_key:
            raise LLMConfigurationError(
                "GEMINI_API_KEY is not configured. Please set GEMINI_API_KEY in environment or .env.",
                provider=self.provider_name,
            )
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
        Generate structured output adhering to *schema* using Gemini generateContent API.
        """
        client = self._get_client()

        # Build contents
        contents: list[dict[str, Any]] = [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ]

        # Build generationConfig with structured output schema
        gemini_schema = _clean_schema_for_gemini(schema)
        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "responseMimeType": "application/json",
            "responseSchema": gemini_schema,
        }

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }

        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}],
            }

        endpoint = f"/v1beta/models/{self._model}:generateContent"
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

        try:
            logger.info(
                "llm.gemini.request",
                model=self._model,
                schema=schema.__name__,
                temperature=temperature,
            )
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            error_body = exc.response.text
            if status_code in (401, 403):
                raise LLMAuthenticationError(
                    f"Gemini authentication failed (HTTP {status_code}): {error_body}",
                    provider=self.provider_name,
                    cause=exc,
                ) from exc
            elif status_code == 429:
                raise LLMAPIError(
                    f"Gemini quota or rate limit exceeded (HTTP 429): {error_body}",
                    provider=self.provider_name,
                    cause=exc,
                ) from exc
            else:
                raise LLMAPIError(
                    f"Gemini API returned HTTP {status_code}: {error_body}",
                    provider=self.provider_name,
                    cause=exc,
                ) from exc
        except httpx.ConnectError as exc:
            raise LLMAPIError(
                f"Failed to connect to Gemini API: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
        except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            raise LLMAPIError(
                f"Gemini request timed out after {self._timeout}s: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMAPIError(
                f"Gemini network request failed: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(
                f"Unexpected error communicating with Gemini API: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc

        try:
            data = response.json()
        except Exception as exc:
            raise LLMAPIError(
                f"Gemini returned non-JSON HTTP response body: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc

        candidates = data.get("candidates")
        if not candidates:
            block_reason = data.get("promptFeedback", {}).get("blockReason", "UNKNOWN")
            raise LLMAPIError(
                f"Gemini returned no response candidates. Block reason: {block_reason}",
                provider=self.provider_name,
            )

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        if finish_reason == "SAFETY":
            raise LLMAPIError(
                "Gemini response candidate was blocked by safety filters.",
                provider=self.provider_name,
            )

        parts = candidate.get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise LLMAPIError(
                f"Gemini response candidate missing text content: {candidate}",
                provider=self.provider_name,
            )

        raw_text = parts[0]["text"]
        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            return schema.model_validate_json(clean_text)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.error(
                "llm.gemini.validation_error",
                schema=schema.__name__,
                content=clean_text[:500],
                error=str(exc),
            )
            raise LLMAPIError(
                f"Failed to parse or validate Gemini output against {schema.__name__}: {exc}",
                provider=self.provider_name,
                cause=exc,
            ) from exc
