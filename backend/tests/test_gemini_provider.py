"""
tests/test_gemini_provider.py
=============================
Focused unit tests for GeminiLLMProvider (Google AI Studio Free Tier).

Verifies:
- Structured output generation using Gemini generateContent REST API.
- Correct payload construction (model, contents, systemInstruction, generationConfig, responseSchema).
- Markdown code-fence stripping.
- Error handling: authentication (401/403), quota/rate limit (429), timeouts, network errors, malformed responses, safety blocks, validation failures.
- Provider factory routing (gemini, openai, ollama).
- Support for complex extraction schemas with nested models.

All tests mock HTTP transport and do NOT make real external API calls.
"""

from __future__ import annotations

import json
from typing import Any
import httpx
from pydantic import BaseModel, Field
import pytest

from app.agents.classification.schemas import DocumentClassification
from app.agents.extraction.schemas import InvoiceExtraction
from app.core.config import settings
from app.core.enums import DocumentType
from app.services.llm.base import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMProvider,
)
from app.services.llm.factory import get_llm_provider
from app.services.llm.gemini import GeminiLLMProvider, _clean_schema_for_gemini
from app.services.llm.ollama import OllamaLLMProvider
from app.services.llm.openai import OpenAILLMProvider


class SampleExtractionSchema(BaseModel):
    document_type: str = Field(description="Type of document")
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str


@pytest.mark.asyncio
async def test_gemini_provider_successful_structured_output():
    """Verify structured output parsing from a successful Gemini generateContent response."""
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        resp_body = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "document_type": "INVOICE",
                                        "confidence": 0.98,
                                        "summary": "Sample tax invoice extraction.",
                                    }
                                )
                            }
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                    "index": 0,
                }
            ]
        }
        return httpx.Response(200, json=resp_body)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://mock-gemini.googleapis.com",
    )
    provider = GeminiLLMProvider(
        api_key="test-gemini-key-12345",
        model="gemini-3.5-flash-lite",
        client=client,
        base_url="https://mock-gemini.googleapis.com",
    )

    result = await provider.generate_structured(
        prompt="Process this invoice text...",
        schema=SampleExtractionSchema,
        system_prompt="You are a document extraction system.",
        temperature=0.0,
    )

    assert isinstance(result, SampleExtractionSchema)
    assert result.document_type == "INVOICE"
    assert result.confidence == 0.98
    assert result.summary == "Sample tax invoice extraction."

    # Verify request payload & headers
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.method == "POST"
    assert "/v1beta/models/gemini-3.5-flash-lite:generateContent" in req.url.path
    assert req.headers["x-goog-api-key"] == "test-gemini-key-12345"

    payload = json.loads(req.content.decode("utf-8"))
    assert payload["contents"][0]["parts"][0]["text"] == "Process this invoice text..."
    assert payload["systemInstruction"]["parts"][0]["text"] == "You are a document extraction system."
    assert payload["generationConfig"]["temperature"] == 0.0
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert "responseSchema" in payload["generationConfig"]


@pytest.mark.asyncio
async def test_gemini_provider_with_markdown_fences():
    """Verify that JSON wrapped in markdown code fences is cleaned and parsed properly."""
    def handler(request: httpx.Request) -> httpx.Response:
        fenced_json = (
            "```json\n"
            "{\n"
            '  "document_type": "INVOICE",\n'
            '  "confidence": 0.95,\n'
            '  "reasoning": "Header contains tax invoice",\n'
            '  "signals": ["tax invoice", "subtotal"]\n'
            "}\n"
            "```"
        )
        resp_body = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": fenced_json}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        return httpx.Response(200, json=resp_body)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://mock-gemini.googleapis.com",
    )
    provider = GeminiLLMProvider(
        api_key="test-key",
        client=client,
        base_url="https://mock-gemini.googleapis.com",
    )

    result = await provider.generate_structured(
        prompt="Classify document",
        schema=DocumentClassification,
    )

    assert isinstance(result, DocumentClassification)
    assert result.document_type == DocumentType.INVOICE
    assert result.confidence == 0.95
    assert "tax invoice" in result.reasoning


@pytest.mark.asyncio
async def test_gemini_provider_nested_extraction_schema_support():
    """Verify that complex nested schemas like InvoiceExtraction work with Gemini."""
    def handler(request: httpx.Request) -> httpx.Response:
        resp_body = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "invoice_number": "INV-2026-001",
                                        "invoice_date": "2026-03-15",
                                        "currency": "USD",
                                        "total_amount": 1375.0,
                                        "vendor": {"name": "Acme Supplies Ltd."},
                                        "line_items": [
                                            {
                                                "description": "Processing Unit",
                                                "quantity": 2.0,
                                                "unit_price": 500.0,
                                                "amount": 1000.0,
                                            }
                                        ],
                                    }
                                )
                            }
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        return httpx.Response(200, json=resp_body)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://mock-gemini.googleapis.com",
    )
    provider = GeminiLLMProvider(
        api_key="test-key",
        client=client,
        base_url="https://mock-gemini.googleapis.com",
    )

    result = await provider.generate_structured(
        prompt="Extract fields",
        schema=InvoiceExtraction,
    )

    assert isinstance(result, InvoiceExtraction)
    assert result.invoice_number == "INV-2026-001"
    assert result.total_amount == 1375.0
    assert result.vendor is not None
    assert result.vendor.name == "Acme Supplies Ltd."
    assert len(result.line_items) == 1
    assert result.line_items[0].description == "Processing Unit"


@pytest.mark.asyncio
async def test_gemini_provider_missing_api_key_configuration_error():
    """Verify that calling Gemini without an API key raises LLMConfigurationError."""
    provider = GeminiLLMProvider(api_key="")
    with pytest.raises(LLMConfigurationError) as exc_info:
        await provider.generate_structured(
            prompt="Hello",
            schema=SampleExtractionSchema,
        )
    assert "GEMINI_API_KEY is not configured" in str(exc_info.value)
    assert exc_info.value.provider == "gemini"


@pytest.mark.asyncio
async def test_gemini_provider_authentication_failure():
    """Verify that HTTP 401/403 responses raise LLMAuthenticationError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"code": 401, "message": "API key not valid. Please pass a valid API key."}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock-gemini.googleapis.com")
    provider = GeminiLLMProvider(api_key="invalid-key", client=client, base_url="https://mock-gemini.googleapis.com")

    with pytest.raises(LLMAuthenticationError) as exc_info:
        await provider.generate_structured(prompt="Hi", schema=SampleExtractionSchema)
    assert "authentication failed" in str(exc_info.value)
    assert exc_info.value.provider == "gemini"


@pytest.mark.asyncio
async def test_gemini_provider_quota_rate_limit_failure():
    """Verify that HTTP 429 raises LLMAPIError identifying rate limit / quota."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota)."}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock-gemini.googleapis.com")
    provider = GeminiLLMProvider(api_key="test-key", client=client, base_url="https://mock-gemini.googleapis.com")

    with pytest.raises(LLMAPIError) as exc_info:
        await provider.generate_structured(prompt="Hi", schema=SampleExtractionSchema)
    assert "quota or rate limit exceeded" in str(exc_info.value)
    assert exc_info.value.provider == "gemini"


@pytest.mark.asyncio
async def test_gemini_provider_malformed_response():
    """Verify that malformed or candidate-less response raises LLMAPIError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock-gemini.googleapis.com")
    provider = GeminiLLMProvider(api_key="test-key", client=client, base_url="https://mock-gemini.googleapis.com")

    with pytest.raises(LLMAPIError) as exc_info:
        await provider.generate_structured(prompt="Hi", schema=SampleExtractionSchema)
    assert "returned no response candidates" in str(exc_info.value)


@pytest.mark.asyncio
async def test_gemini_provider_safety_block_handling():
    """Verify that finishReason=SAFETY raises LLMAPIError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"candidates": [{"finishReason": "SAFETY"}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock-gemini.googleapis.com")
    provider = GeminiLLMProvider(api_key="test-key", client=client, base_url="https://mock-gemini.googleapis.com")

    with pytest.raises(LLMAPIError) as exc_info:
        await provider.generate_structured(prompt="Blocked prompt", schema=SampleExtractionSchema)
    assert "blocked by safety filters" in str(exc_info.value)


@pytest.mark.asyncio
async def test_gemini_provider_schema_validation_failure():
    """Verify that model output that violates schema constraints raises LLMAPIError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps({"document_type": "INVOICE", "confidence": "not-a-number"})
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock-gemini.googleapis.com")
    provider = GeminiLLMProvider(api_key="test-key", client=client, base_url="https://mock-gemini.googleapis.com")

    with pytest.raises(LLMAPIError) as exc_info:
        await provider.generate_structured(prompt="Hi", schema=SampleExtractionSchema)
    assert "Failed to parse or validate Gemini output" in str(exc_info.value)


@pytest.mark.asyncio
async def test_gemini_provider_network_failure():
    """Verify network connection errors raise LLMAPIError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock-gemini.googleapis.com")
    provider = GeminiLLMProvider(api_key="test-key", client=client, base_url="https://mock-gemini.googleapis.com")

    with pytest.raises(LLMAPIError) as exc_info:
        await provider.generate_structured(prompt="Hi", schema=SampleExtractionSchema)
    assert "Failed to connect to Gemini API" in str(exc_info.value)


def test_provider_factory_routing():
    """Verify that get_llm_provider correctly routes gemini, openai, and ollama."""
    get_llm_provider.cache_clear()

    gemini_p = get_llm_provider("gemini")
    assert isinstance(gemini_p, GeminiLLMProvider)
    assert gemini_p.provider_name == "gemini"

    openai_p = get_llm_provider("openai")
    assert isinstance(openai_p, OpenAILLMProvider)
    assert openai_p.provider_name == "openai"

    ollama_p = get_llm_provider("ollama")
    assert isinstance(ollama_p, OllamaLLMProvider)
    assert ollama_p.provider_name == "ollama"

    with pytest.raises(NotImplementedError):
        get_llm_provider("google")

    get_llm_provider.cache_clear()


def test_clean_schema_for_gemini():
    """Verify _clean_schema_for_gemini dereferences nested models and removes title/default."""
    cleaned = _clean_schema_for_gemini(InvoiceExtraction)
    cleaned_json = json.dumps(cleaned)
    assert "$defs" not in cleaned
    assert "$ref" not in cleaned_json
    assert "properties" in cleaned
    assert "line_items" in cleaned["properties"]
    assert "vendor" in cleaned["properties"]
