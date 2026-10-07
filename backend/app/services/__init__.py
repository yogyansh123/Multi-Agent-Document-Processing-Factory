"""
services/__init__.py
====================
Business logic and external service integrations.

Sub-packages provide provider abstractions behind clean interfaces:

- ocr/          — OCR provider abstraction (Tesseract, AWS Textract, etc.)
- llm/          — LLM provider abstraction (OpenAI, Anthropic, Google, etc.)
- vector_store/ — Vector database abstraction (ChromaDB, Pinecone, etc.)

Architecture rule: Services contain all business logic.
                   Agents call services; routes call services.
                   Services do NOT import from agents or routes.
"""
