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
    "published work. If the context includes an uploaded document excerpt, you "
    "may use it and cite it as (document name, page N)."
)


def _groq_keys():
    keys = []
    for v in (config.GROQ_API_KEY, config.GROQ_API_KEY2):
        keys += [k.strip() for k in (v or "").split(",") if k.strip()]
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _is_rate_limit(exc) -> bool:
    s = str(exc).lower()
    return ("rate_limit" in s or "429" in s or "tokens per day" in s
            or getattr(exc, "status_code", None) == 429)


def _create(**kw):
    """One completion. Uses the self-hosted OpenAI endpoint if configured;
    otherwise Groq with automatic key failover on a daily/rate limit."""
    if config.LLM_PROVIDER == "openai" or config.LLM_BASE_URL:
        from openai import OpenAI

        client = OpenAI(base_url=config.LLM_BASE_URL or None,
                        api_key=config.LLM_API_KEY or "not-needed")
        return client.chat.completions.create(**kw)

    keys = _groq_keys()
    if not keys:
        raise RuntimeError(
            "No LLM configured. Set GROQ_API_KEY (https://console.groq.com/keys), "
            "or LLM_BASE_URL for a self-hosted OpenAI-compatible endpoint."
        )
    from groq import Groq

    last = None
    for i, key in enumerate(keys):
        try:
            return Groq(api_key=key).chat.completions.create(**kw)
        except Exception as exc:
            last = exc
            if _is_rate_limit(exc) and i < len(keys) - 1:
                continue
            raise
    raise last


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


def stream_answer(question: str, context: str, history: List[Dict],
                  model: str = None) -> Iterator[str]:
    """Yield the answer token-by-token for a live typing effect."""
    messages = build_messages(question, context, history)
    completion = _create(
        model=model or config.LLM_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
        stream=True,
    )
    for chunk in completion:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
