"""Groq-backed generation using open-source models (Llama 3, Mixtral, ...).

Replaces the original IBM Watson Machine Learning dependency.
"""
from typing import Iterator, List, Dict

from groq import Groq

from . import config

SYSTEM_PROMPT = (
    "You are DrJhaGPT, the AI assistant for Dr. Pranay Jha, an enterprise "
    "infrastructure expert who writes about VMware, cloud, datacenters, and AI "
    "at drpranayjha.com. Answer clearly and professionally using Markdown.\n\n"
    "When context from Dr. Jha's articles is provided, base your answer on it. "
    "Each context item includes a Title and a URL. When you reference an "
    "article, cite it as a Markdown link using its exact URL, e.g. "
    "[Article Title](https://drpranayjha.com/...). Only use URLs given in the "
    "context — never invent titles, URLs, or placeholder links like (#). "
    "If the context does not contain the answer, say so briefly and then answer "
    "from general knowledge, making it clear that part is not from his "
    "published work."
)


def _client() -> Groq:
    if not config.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your "
            "free key from https://console.groq.com/keys"
        )
    return Groq(api_key=config.GROQ_API_KEY)


def build_messages(question: str, context: str, history: List[Dict]) -> List[Dict]:
    """Assemble the chat payload: system + prior turns + grounded user turn."""
    messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)

    if context:
        user_content = (
            "Use the following excerpts from Dr. Pranay Jha's articles to answer.\n\n"
            f"---\n{context}\n---\n\nQuestion: {question}"
        )
    else:
        user_content = question

    messages.append({"role": "user", "content": user_content})
    return messages


def stream_answer(question: str, context: str, history: List[Dict]) -> Iterator[str]:
    """Yield the answer token-by-token for a live typing effect."""
    messages = build_messages(question, context, history)
    completion = _client().chat.completions.create(
        model=config.GROQ_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
        stream=True,
    )
    for chunk in completion:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
