"""
services/rag/context.py
=======================
Context assembly for RAG grounded generation.

Formats retrieved document chunks with clear source markers and enforces
maximum context window character boundaries.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.rag.retrieval import RetrievedChunk


def assemble_rag_context(
    chunks: list[RetrievedChunk],
    max_chars: int | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Format retrieved chunks into a structured context string with source citations.

    Returns:
        tuple of (context_text: str, source_citations: list[dict])
    """
    if not chunks:
        return "", []

    max_limit = max_chars or settings.RAG_MAX_CONTEXT_CHARS
    context_blocks: list[str] = []
    citations: list[dict[str, Any]] = []
    current_length = 0

    for idx, chunk in enumerate(chunks, start=1):
        source_header = (
            f"[Source {idx}]\n"
            f"Document: {chunk.filename}\n"
            f"Document Type: {chunk.document_type or 'OTHER'}\n"
            f"Page: {chunk.page_number if chunk.page_number is not None else 'N/A'}\n"
            f"Content:\n"
        )
        content_body = chunk.content.strip()
        block = f"{source_header}{content_body}\n"

        if current_length + len(block) > max_limit:
            # Check if partial content fits
            remaining_chars = max_limit - current_length - len(source_header) - 20
            if remaining_chars > 100:
                truncated_body = content_body[:remaining_chars] + "... [truncated]"
                block = f"{source_header}{truncated_body}\n"
                context_blocks.append(block)
                citations.append({
                    "source_number": idx,
                    "chunk_id": str(chunk.chunk_id),
                    "document_id": str(chunk.document_id),
                    "filename": chunk.filename,
                    "document_type": chunk.document_type,
                    "page_number": chunk.page_number,
                    "similarity_score": chunk.similarity_score,
                    "excerpt": truncated_body[:200],
                })
            break

        context_blocks.append(block)
        current_length += len(block) + 1
        citations.append({
            "source_number": idx,
            "chunk_id": str(chunk.chunk_id),
            "document_id": str(chunk.document_id),
            "filename": chunk.filename,
            "document_type": chunk.document_type,
            "page_number": chunk.page_number,
            "similarity_score": chunk.similarity_score,
            "excerpt": content_body[:200] + ("..." if len(content_body) > 200 else ""),
        })

    full_context = "\n".join(context_blocks).strip()
    return full_context, citations
