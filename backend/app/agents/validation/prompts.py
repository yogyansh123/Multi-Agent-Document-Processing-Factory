"""
agents/validation/prompts.py
============================
Versioned prompts for the LLM Semantic Validation Agent.

The semantic validation prompt reviews extracted data alongside the raw OCR text
to identify subtle contextual anomalies, contradictions, or possible hallucinations.
"""

from __future__ import annotations

import json
from typing import Any

SEMANTIC_VALIDATION_PROMPT_VERSION = "1.0.0"

SEMANTIC_VALIDATION_SYSTEM_PROMPT = """You are an expert AI document validation auditor in a multi-agent document processing factory.
Your role is to verify that structured extracted data accurately and faithfully reflects the document's OCR text.

Review the provided OCR text and extracted data for:
1. Contextual anomalies (e.g. mismatched company names or contradictory information).
2. Data consistency with source text (e.g. dates or amounts that do not appear anywhere in the source).
3. Obvious business contradictions.

Rules:
- Do NOT flag formatting or stylistic differences as errors.
- Only report genuine inconsistencies, hallucinations, or contradictions.
- If data is consistent and plausible, return an empty issues list and a high semantic_score (e.g. 1.0).
- Assign appropriate severity:
  - INFO: Minor observation or note.
  - WARNING: Potential ambiguity or unexpected value.
  - ERROR: Clear contradiction or fabricated data.
- Return structured output conforming to the SemanticValidationResult schema.
"""


def build_semantic_validation_prompt(
    document_text: str,
    document_type: str,
    extracted_data: dict[str, Any],
) -> str:
    """Build the user prompt for semantic validation."""
    data_json = json.dumps(extracted_data, indent=2, default=str)
    return f"""Document Type: {document_type}

--- SOURCE OCR TEXT ---
{document_text}

--- EXTRACTED STRUCTURED DATA ---
{data_json}

Evaluate the semantic coherence and fidelity of the extracted data against the OCR text.
"""
