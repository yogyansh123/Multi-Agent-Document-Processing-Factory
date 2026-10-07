"""
agents/classification/graph.py
==============================
LangGraph state graph definition for the Document Classification Agent.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.classification.nodes import (
    create_classify_document_node,
    create_load_document_text_node,
    create_persist_classification_node,
)
from app.agents.classification.state import ClassificationState
from app.services.llm.base import LLMProvider


def _route_after_load(state: ClassificationState) -> Literal["classify_document", "__end__"]:
    if state.get("error"):
        return END
    return "classify_document"


def _route_after_classify(state: ClassificationState) -> Literal["persist_classification", "__end__"]:
    if state.get("error"):
        return END
    return "persist_classification"


def create_classification_graph(
    llm_provider: LLMProvider,
    db: AsyncSession | None = None,
) -> CompiledStateGraph:
    """
    Construct and compile the Classification Agent LangGraph workflow.

    Workflow:
    START
      ↓
    load_document_text  (verifies OCR status, retrieves text)
      ↓ (conditional: error ? END : classify_document)
    classify_document   (calls LLMProvider with structured schema)
      ↓ (conditional: error ? END : persist_classification)
    persist_classification (updates Document status to CLASSIFIED and saves)
      ↓
    END
    """
    workflow = StateGraph(ClassificationState)

    workflow.add_node("load_document_text", create_load_document_text_node(db))
    workflow.add_node("classify_document", create_classify_document_node(llm_provider))
    workflow.add_node("persist_classification", create_persist_classification_node(db))

    workflow.add_edge(START, "load_document_text")
    workflow.add_conditional_edges(
        "load_document_text",
        _route_after_load,
        {
            "classify_document": "classify_document",
            END: END,
        },
    )
    workflow.add_conditional_edges(
        "classify_document",
        _route_after_classify,
        {
            "persist_classification": "persist_classification",
            END: END,
        },
    )
    workflow.add_edge("persist_classification", END)

    return workflow.compile()
