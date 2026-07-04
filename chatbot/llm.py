"""LLM generation via Groq (default) or any OpenAI-compatible endpoint.

Set LLM_PROVIDER=openai (or LLM_BASE_URL) to use a self-hosted model server
(vLLM / Ollama / NVIDIA NIM) for on-prem / air-gapped deployments.
"""
from typing import Iterator, List, Dict

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


def _client():
    """Groq by default, or any OpenAI-compatible endpoint (vLLM / Ollama / NIM)
    when LLM_PROVIDER=openai or LLM_BASE_URL is set."""
    if config.LLM_PROVIDER == "openai" or config.LLM_BASE_URL:
        from openai import OpenAI

        return OpenAI(base_url=config.LLM_BASE_URL or None,
                      api_key=config.LLM_API_KEY or "not-needed")
    if not config.GROQ_API_KEY:
        raise RuntimeError(
            "No LLM configured. Set GROQ_API_KEY (https://console.groq.com/keys), "
            "or LLM_BASE_URL for a self-hosted OpenAI-compatible endpoint."
        )
    from groq import Groq

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
        model=config.LLM_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
        stream=True,
    )
    for chunk in completion:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
