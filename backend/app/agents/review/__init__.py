"""
agents/review/__init__.py
==========================
Human Review Routing Agent.

Manages the human-in-the-loop review queue:

- Routes documents to human reviewers when confidence < threshold
- Routes documents to auto-approval when confidence >= threshold
- Manages reviewer assignments
- Tracks review actions (approve / reject / correct)
- Triggers reprocessing after corrections

This agent interfaces with the review queue API and the notification service.
"""
