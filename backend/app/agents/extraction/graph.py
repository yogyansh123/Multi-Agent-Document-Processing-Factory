"""
agents/extraction/graph.py
==========================
LangGraph state graph definition for the Information Extraction Agent.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.extraction.nodes import (
    create_extract_information_node,
    create_load_classification_node,
    create_load_document_node,
    create_persist_extraction_node,
    create_select_schema_node,
)
from app.agents.extraction.state import ExtractionState
from app.services.llm.base import LLMProvider


def _check_error(next_node: str):
    """Factory creating an edge condition that short-circuits to END on error."""

    def condition(state: ExtractionState) -> Literal["continue", "__end__"]:
        if state.get("error"):
            return END
        return "continue"

    return condition


def create_extraction_graph(
    llm_provider: LLMProvider,
    db: AsyncSession | None = None,
) -> CompiledStateGraph:
    """
    Construct and compile the Information Extraction Agent LangGraph workflow.

    Workflow:
    START
      ↓
    load_document          (retrieves OCR text, verifies OCR completion)
      ↓ (error ? END)
    load_classification    (verifies classification completed)
      ↓ (error ? END)
    select_schema          (identifies Pydantic schema for document type)
      ↓ (error ? END)
    extract_information    (calls LLMProvider with structured schema)
      ↓ (error ? END)
    persist_extraction     (updates Document status to EXTRACTED and saves)
      ↓
    END
    """
    workflow = StateGraph(ExtractionState)

    workflow.add_node("load_document", create_load_document_node(db))
    workflow.add_node("load_classification", create_load_classification_node(db))
    workflow.add_node("select_schema", create_select_schema_node())
    workflow.add_node("extract_information", create_extract_information_node(llm_provider))
    workflow.add_node("persist_extraction", create_persist_extraction_node(db))

    workflow.add_edge(START, "load_document")

    workflow.add_conditional_edges(
        "load_document",
        _check_error("load_classification"),
        {"continue": "load_classification", END: END},
    )
    workflow.add_conditional_edges(
        "load_classification",
        _check_error("select_schema"),
        {"continue": "select_schema", END: END},
    )
    workflow.add_conditional_edges(
        "select_schema",
        _check_error("extract_information"),
        {"continue": "extract_information", END: END},
    )
    workflow.add_conditional_edges(
        "extract_information",
        _check_error("persist_extraction"),
        {"continue": "persist_extraction", END: END},
    )
    workflow.add_edge("persist_extraction", END)

    return workflow.compile()
