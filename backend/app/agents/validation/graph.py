"""
agents/validation/graph.py
==========================
LangGraph workflow definition for the Document Validation Agent.

Flow:
    START
      ↓
    load_document (short-circuit on missing document/prerequisites)
      ↓
    load_extraction (short-circuit if extracted_data is missing)
      ↓
    run_deterministic_validation
      ↓
    run_semantic_validation (LLM-assisted consistency check)
      ↓
    combine_validation_results (composite score & validity flag)
      ↓
    persist_validation
      ↓
    END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.validation.nodes import (
    combine_validation_results,
    load_document,
    load_extraction,
    persist_validation,
    run_deterministic_validation,
    run_semantic_validation,
)
from app.agents.validation.state import ValidationState
from app.services.llm.base import LLMProvider


def _check_error(state: ValidationState) -> str:
    """Routing helper: stop immediately if an error occurred in a node."""
    if state.get("error"):
        return END
    return "next"


def create_validation_graph(
    llm_provider: LLMProvider | None = None,
    db: AsyncSession | None = None,
):
    """
    Construct and compile the Validation Agent StateGraph.

    Args:
        llm_provider: Provider instance for semantic validation (or None for deterministic only).
        db: Async database session for persistence (or None for standalone testing).
    """
    workflow = StateGraph(ValidationState)

    async def _load_doc_node(state: ValidationState) -> dict:
        return await load_document(state, db=db)

    async def _semantic_node(state: ValidationState) -> dict:
        return await run_semantic_validation(state, llm_provider=llm_provider)

    async def _persist_node(state: ValidationState) -> dict:
        return await persist_validation(state, db=db)

    workflow.add_node("load_document", _load_doc_node)
    workflow.add_node("load_extraction", load_extraction)
    workflow.add_node("run_deterministic_validation", run_deterministic_validation)
    workflow.add_node("run_semantic_validation", _semantic_node)
    workflow.add_node("combine_validation_results", combine_validation_results)
    workflow.add_node("persist_validation", _persist_node)

    # Add edges
    workflow.add_edge(START, "load_document")

    workflow.add_conditional_edges(
        "load_document",
        _check_error,
        {"next": "load_extraction", END: END},
    )

    workflow.add_conditional_edges(
        "load_extraction",
        _check_error,
        {"next": "run_deterministic_validation", END: END},
    )

    workflow.add_edge("run_deterministic_validation", "run_semantic_validation")
    workflow.add_edge("run_semantic_validation", "combine_validation_results")
    workflow.add_edge("combine_validation_results", "persist_validation")
    workflow.add_edge("persist_validation", END)

    return workflow.compile()
