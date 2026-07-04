"""Public retrieval interface for the app.

Delegates retrieval to the Phase 1 hybrid + rerank pipeline in `retrieval.py`,
keeping the same API the UI expects (has_knowledge / retrieve / format_context).
"""
from typing import List, Dict

from . import retrieval


def has_knowledge() -> bool:
    return retrieval.has_knowledge()


def retrieve(question: str) -> List[Dict]:
    return retrieval.retrieve(question)


def format_context(results: List[Dict]) -> str:
    """Render retrieved chunks into a compact context block for the LLM."""
    blocks = []
    for r in results:
        blocks.append(
            f"Title: {r.get('title', 'Article')}\n"
            f"URL: {r.get('url', '')}\n"
            f"{r.get('text', '')}"
        )
    return "\n\n".join(blocks)
