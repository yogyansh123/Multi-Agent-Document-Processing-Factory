"""
agents/validation/state.py
==========================
State definition for the LangGraph Validation Agent.

The validation workflow maintains strongly typed state throughout:
1. Loading document & extraction
2. Running deterministic rules
3. Running semantic LLM validation
4. Combining issues and computing validation score
5. Persisting results
"""

from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict


class ValidationState(TypedDict, total=False):
    """
    Strongly typed state dictionary flowing through the Validation Agent graph.
    """

    # Input identifiers & source data
    document_id: str
    document_text: str
    document_type: str
    extracted_data: dict[str, Any]

    # Intermediate validation outputs
    deterministic_issues: list[dict[str, Any]]
    semantic_issues: list[dict[str, Any]]
    rules_checked: list[str]
    semantic_score: float

    # Final combined validation outcome
    validation_result: dict[str, Any] | None
    validation_score: float | None
    is_valid: bool | None

    # Error handling
    error: str | None
