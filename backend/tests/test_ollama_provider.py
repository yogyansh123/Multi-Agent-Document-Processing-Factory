"""
tests/test_ollama_provider.py
=============================
Unit tests for OllamaLLMProvider.

Verifies:
- Native structured output generation with Ollama /api/chat.
- Correct payload construction (model, messages, format json_schema, options).
- System prompt preservation.
- Error handling for connection errors, timeouts, HTTP errors, malformed JSON, and validation failures.
- Factory integration.

All tests mock the HTTP transport and do NOT require a running Ollama server.
"""

from __future__ import annotations

import json
from typing import Any
import httpx
from pydantic import BaseModel, Field
import pytest

from app.core.config import settings
from app.services.llm.base import (
    LLMAPIError,
    LLMConfigurationError,
    LLMError,
    LLMProvider,
)
from app.services.llm.factory import get_llm_provider
from app.services.llm.ollama import OllamaLLMProvider


class SampleExtractionSchema(BaseModel):
    document_type: str = Field(description="Type of document")
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str


@pytest.fixture
def mock_ollama_transport():
    """Helper creating mock httpx transports for Ollama responses."""

    def _create(handler):
        return httpx.MockTransport(handler)

    return _create


@pytest.mark.asyncio
async def test_ollama_provider_successful_structured_output():
    """Verify structured output parsing from a successful Ollama /api/chat response."""
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        resp_body = {
            "model": "llama3.2:3b",
            "created_at": "2026-09-29T22:00:00Z",
            "message": {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "document_type": "INVOICE",
                        "confidence": 0.96,
                        "summary": "Sample invoice extraction summary.",
                    }
                ),
            },
            "done": True,
        }
        return httpx.Response(200, json=resp_body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://mock-ollama:11434")
    provider = OllamaLLMProvider(
        base_url="http://mock-ollama:11434",
        model="llama3.2:3b",
        client=client,
    )

    result = await provider.generate_structured(
        prompt="Extract information from this invoice text...",
        schema=SampleExtractionSchema,
        system_prompt="You are a precise document extractor.",
        temperature=0.0,
    )

    assert isinstance(result, SampleExtractionSchema)
    assert result.document_type == "INVOICE"
    assert result.confidence == 0.96
    assert result.summary == "Sample invoice extraction summary."

    # Verify request payload
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.method == "POST"
    assert req.url.path == "/api/chat"

    payload = json.loads(req.content.decode("utf-8"))
    assert payload["model"] == "llama3.2:3b"
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0.0

    # Verify messages preservation
    assert payload["messages"] == [
        {"role": "system", "content": "You are a precise document extractor."},
        {"role": "user", "content": "Extract information from this invoice text..."},
    ]

    # Verify format is schema JSON schema
    expected_schema = SampleExtractionSchema.model_json_schema()
    assert payload["format"] == expected_schema

    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_no_system_prompt():
    """Verify messages payload when system_prompt is None."""
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": '{"document_type": "RECEIPT", "confidence": 0.88, "summary": "Gas receipt"}',
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://mock-ollama:11434")
    provider = OllamaLLMProvider(base_url="http://mock-ollama:11434", client=client)

    result = await provider.generate_structured(
        prompt="Classify this receipt",
        schema=SampleExtractionSchema,
        system_prompt=None,
    )

    assert result.document_type == "RECEIPT"
    assert len(captured_requests) == 1
    payload = json.loads(captured_requests[0].content.decode("utf-8"))
    assert payload["messages"] == [
        {"role": "user", "content": "Classify this receipt"},
    ]

    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_malformed_json_response():
    """Verify LLMAPIError is raised when Ollama returns non-JSON content."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "This is raw text, not valid JSON."}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://mock-ollama:11434")
    provider = OllamaLLMProvider(base_url="http://mock-ollama:11434", client=client)

    with pytest.raises(LLMAPIError, match="Failed to parse or validate Ollama output"):
        await provider.generate_structured("test", SampleExtractionSchema)

    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_schema_validation_failure():
    """Verify LLMAPIError is raised when JSON does not conform to the schema constraints."""

    def handler(request: httpx.Request) -> httpx.Response:
        # confidence is outside [0.0, 1.0] range
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": '{"document_type": "INVOICE", "confidence": 2.5, "summary": "test"}',
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://mock-ollama:11434")
    provider = OllamaLLMProvider(base_url="http://mock-ollama:11434", client=client)

    with pytest.raises(LLMAPIError, match="Failed to parse or validate Ollama output"):
        await provider.generate_structured("test", SampleExtractionSchema)

    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_http_500_error():
    """Verify LLMAPIError is raised when Ollama returns an HTTP 500 error."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Ollama GPU/CPU error")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://mock-ollama:11434")
    provider = OllamaLLMProvider(base_url="http://mock-ollama:11434", client=client)

    with pytest.raises(LLMAPIError, match="Ollama API returned HTTP 500"):
        await provider.generate_structured("test", SampleExtractionSchema)

    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_connection_error():
    """Verify LLMAPIError is raised when connection to Ollama fails."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused to 127.0.0.1:11434", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://mock-ollama:11434")
    provider = OllamaLLMProvider(base_url="http://mock-ollama:11434", client=client)

    with pytest.raises(LLMAPIError, match="Failed to connect to Ollama"):
        await provider.generate_structured("test", SampleExtractionSchema)

    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_timeout_error():
    """Verify LLMAPIError is raised when the Ollama request times out."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Read timed out after 120s", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://mock-ollama:11434")
    provider = OllamaLLMProvider(base_url="http://mock-ollama:11434", timeout=60.0, client=client)

    with pytest.raises(LLMAPIError, match="Ollama request timed out after 60.0s"):
        await provider.generate_structured("test", SampleExtractionSchema)

    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_empty_content_error():
    """Verify LLMAPIError is raised when Ollama returns empty message content."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"role": "assistant", "content": ""}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://mock-ollama:11434")
    provider = OllamaLLMProvider(base_url="http://mock-ollama:11434", client=client)

    with pytest.raises(LLMAPIError, match="Ollama returned empty or invalid response content"):
        await provider.generate_structured("test", SampleExtractionSchema)

    await provider.aclose()


def test_ollama_provider_properties():
    """Verify provider name, defaults, and configuration properties."""
    provider = OllamaLLMProvider(
        base_url="http://custom-ollama:11434",
        model="custom-model:7b",
        timeout=45.0,
    )
    assert provider.provider_name == "ollama"
    assert provider._base_url == "http://custom-ollama:11434"
    assert provider._model == "custom-model:7b"
    assert provider._timeout == 45.0
    assert isinstance(provider, LLMProvider)


def test_ollama_provider_missing_base_url():
    """Verify LLMConfigurationError is raised if base_url is explicitly empty."""
    with pytest.raises(LLMConfigurationError, match="OLLAMA_BASE_URL is not configured"):
        OllamaLLMProvider(base_url="")
