"""
services/rag/embeddings.py
==========================
Embedding provider abstraction for semantic vector search.

Provides:
- EmbeddingProvider (abstract base interface)
- OpenAIEmbeddingProvider (official OpenAI embeddings)
- FakeEmbeddingProvider (deterministic, zero-external-API provider for testing)
- Factory function get_embedding_provider()
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.services.rag.embeddings")


class EmbeddingProviderError(Exception):
    """Base exception for embedding provider errors."""


class EmbeddingProvider(ABC):
    """Abstract base class for vector embedding generation."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality produced by this provider."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate a dense vector embedding for a single query or text string."""

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate dense vector embeddings for a list of document chunks."""


class FakeEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic in-memory embedding generator for testing and offline environments.
    Produces unit-normalized float vectors based on SHA-256 hashes of input text.
    """

    def __init__(self, dimension: int | None = None) -> None:
        self._dimension = dimension or settings.EMBEDDING_DIMENSION

    @property
    def dimension(self) -> int:
        return self._dimension

    def _generate_vector(self, text: str) -> list[float]:
        """Deterministically create a unit-length non-negative vector from text words and hash."""
        if not text:
            return [1.0 / math.sqrt(self._dimension)] * self._dimension

        vec = [0.0] * self._dimension
        words = re.findall(r"\w+", text.lower())
        for word in words:
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            vec[h % self._dimension] += 2.0
            vec[(h >> 16) % self._dimension] += 1.0

        # Add small deterministic non-negative background component from SHA-256
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        for i in range(self._dimension):
            b = digest[i % len(digest)]
            vec[i] += 0.05 * (float(b) / 255.0)

        # Normalize to unit length (L2 norm)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return [1.0 / math.sqrt(self._dimension)] * self._dimension
        return [round(v / norm, 6) for v in vec]

    async def embed_text(self, text: str) -> list[float]:
        return self._generate_vector(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._generate_vector(t) for t in texts]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI embedding provider implementation using the official async client.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_EMBEDDING_MODEL
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        self._client = None

        if self.api_key:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("openai_package_not_installed")

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_text(self, text: str) -> list[float]:
        if not self._client:
            raise EmbeddingProviderError(
                "OpenAI client is not configured (missing OPENAI_API_KEY)."
            )
        try:
            resp = await self._client.embeddings.create(
                input=text,
                model=self.model,
            )
            return resp.data[0].embedding
        except Exception as exc:
            logger.error("openai_embedding_failed", error=str(exc))
            raise EmbeddingProviderError(f"Failed to generate OpenAI embedding: {exc}") from exc

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._client:
            raise EmbeddingProviderError(
                "OpenAI client is not configured (missing OPENAI_API_KEY)."
            )

        # Batch in chunks of 100 to adhere to API rate limits
        batch_size = 100
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                resp = await self._client.embeddings.create(
                    input=batch,
                    model=self.model,
                )
                sorted_data = sorted(resp.data, key=lambda d: d.index)
                all_embeddings.extend([d.embedding for d in sorted_data])
            except Exception as exc:
                logger.error("openai_batch_embedding_failed", error=str(exc))
                raise EmbeddingProviderError(
                    f"Failed to generate OpenAI batch embeddings: {exc}"
                ) from exc

        return all_embeddings


def get_embedding_provider(
    provider_name: str | None = None,
) -> EmbeddingProvider:
    """
    Factory function returning the configured EmbeddingProvider singleton.
    Falls back gracefully to FakeEmbeddingProvider if no API key is set.
    """
    name = (provider_name or "openai").lower()
    if name == "fake" or not settings.OPENAI_API_KEY:
        return FakeEmbeddingProvider()

    if name == "openai":
        return OpenAIEmbeddingProvider()

    logger.warning("unknown_embedding_provider_fallback", requested=name)
    return FakeEmbeddingProvider()
