"""
agents/confidence/__init__.py
==============================
Confidence Scoring Agent.

Computes per-field and document-level confidence scores:

- Aggregates field-level confidence from the extraction agent
- Applies penalties for validation failures
- Applies bonuses for cross-validated fields
- Produces a final document confidence score (0.0 – 1.0)
- Determines routing: auto-approve vs. human review queue

The confidence threshold is configurable via CONFIDENCE_THRESHOLD in .env.
Documents below the threshold are routed to the human review queue.
"""
