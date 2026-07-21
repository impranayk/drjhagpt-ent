"""LLM generation via Groq (default), Google Gemini, or any OpenAI-compatible endpoint.

Providers, in order:
  * Groq       - the default. GROQ_API_KEY may hold several comma-separated keys,
                 and GROQ_API_KEY2 adds a second account; all are tried in turn.
  * Gemini     - free tier. Used when a Gemini model is picked explicitly, and
                 automatically once every Groq key has hit its daily limit, so a
                 lab guide never dies half-written.
  * OpenAI-compatible - set LLM_PROVIDER=openai / LLM_BASE_URL for a self-hosted
                 model server (vLLM / Ollama / NVIDIA NIM) on-prem or air-gapped.

Two shapes of call:
  * stream_answer() - the grounded RAG chat (the "Ask" tool).
  * generate() / refine() - the studio's document generators.
"""
import json
from functools import lru_cache
from typing import Iterator, List, Dict

from . import config
from .prompts import BASE_SYSTEM

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
    "may use it and cite it as (document name, page N).\n\n"
    "Never invent a command flag, API field, default value or product capability. "
    "If you are unsure whether something exists in the version being discussed, "
    "say so rather than guessing. Put commands and config in fenced code blocks "
    "with a language tag."
)


@lru_cache(maxsize=8)
def _groq_client(key: str):
    """One Groq client per API key, reused across requests.

    Building a client per call creates an httpx connection pool that is then
    thrown away - and because the streaming helpers are generators, a user
    clicking away mid-answer abandons one with the HTTP stream still open.
    """
    from groq import Groq
    return Groq(api_key=key)


def _groq_keys():
    """Every configured Groq key, in failover order."""
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
    return ("rate_limit" in s or "429" in s or "quota" in s or "tokens per day" in s
            or getattr(exc, "status_code", None) == 429)


# --- Google Gemini -----------------------------------------------------------
# Called over plain REST/SSE with httpx (already an indirect dependency) rather
# than adding the google SDK to the boot path.
_GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
               "{model}:streamGenerateContent?alt=sse")


def _to_gemini(messages: List[Dict]):
    """OpenAI-style messages -> Gemini 'contents' + 'systemInstruction'."""
    system, contents = [], []
    for m in messages:
        role, text = m.get("role"), (m.get("content") or "")
        if role == "system":
            system.append(text)
            continue
        contents.append({"role": "model" if role == "assistant" else "user",
                         "parts": [{"text": text}]})
    body = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system)}]}
    return body


def _gemini_stream(messages, model, temperature, max_tokens) -> Iterator[str]:
    import httpx

    key = config.GEMINI_API_KEY
    if not key:
        raise RuntimeError("Gemini isn't configured - set GEMINI_API_KEY.")
    body = _to_gemini(messages)
    body["generationConfig"] = {"temperature": temperature,
                                "maxOutputTokens": max_tokens}
    # The key travels in a header, never the query string, so it can't leak into logs.
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    with httpx.stream("POST", _GEMINI_URL.format(model=model), headers=headers,
                      json=body, timeout=120) as r:
        if r.status_code >= 400:
            r.read()
            raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:300]}")
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                chunk = json.loads(payload)
            except ValueError:
                continue
            for cand in chunk.get("candidates", []):
                for part in (cand.get("content") or {}).get("parts", []):
                    if part.get("text"):
                        yield part["text"]


def _stream(messages: List[Dict], model: str = None, temperature: float = 0.4,
            max_tokens: int = 1400) -> Iterator[str]:
    """Stream a completion, failing over across Groq keys and then to Gemini."""
    kw = dict(model=model or config.LLM_MODEL, messages=messages,
              temperature=temperature, max_tokens=max_tokens, stream=True)

    # Self-hosted OpenAI-compatible endpoint (on-prem): single client, no failover.
    if config.LLM_PROVIDER == "openai" or config.LLM_BASE_URL:
        from openai import OpenAI

        client = OpenAI(base_url=config.LLM_BASE_URL or None,
                        api_key=config.LLM_API_KEY or "not-needed")
        for chunk in client.chat.completions.create(**kw):
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
        return

    # A Gemini model was picked explicitly -> go straight there.
    if config.is_gemini(kw["model"]):
        yield from _gemini_stream(messages, kw["model"], temperature, max_tokens)
        return

    keys = _groq_keys()
    if not keys:
        if config.GEMINI_READY:                  # Gemini alone is a valid setup
            yield from _gemini_stream(messages, config.GEMINI_MODELS[0],
                                      temperature, max_tokens)
            return
        raise RuntimeError(
            "No LLM configured. Set GROQ_API_KEY (https://console.groq.com/keys) "
            "or GEMINI_API_KEY (https://aistudio.google.com/apikey), or LLM_BASE_URL "
            "for a self-hosted OpenAI-compatible endpoint."
        )
    last = None
    for i, key in enumerate(keys):
        try:
            completion = _groq_client(key).chat.completions.create(**kw)
        except Exception as exc:                 # daily limit -> try the next key
            last = exc
            if _is_rate_limit(exc) and i < len(keys) - 1:
                continue
            break
        for chunk in completion:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
        return

    # Every Groq key is spent: carry on with Gemini's free tier if configured,
    # rather than failing mid-document.
    if last is not None and _is_rate_limit(last) and config.GEMINI_READY:
        yield from _gemini_stream(messages, config.GEMINI_MODELS[0],
                                  temperature, max_tokens)
        return
    if last:
        raise last


def _create(**kw):
    """One non-streaming completion (kept for callers that don't stream)."""
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
    last = None
    for i, key in enumerate(keys):
        try:
            return _groq_client(key).chat.completions.create(**kw)
        except Exception as exc:
            last = exc
            if _is_rate_limit(exc) and i < len(keys) - 1:
                continue
            raise
    raise last


# --- The Ask tool (grounded RAG chat) ----------------------------------------
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
    return _stream(build_messages(question, context, history),
                   model=model, temperature=0.3, max_tokens=1400)


# --- The studio generators ---------------------------------------------------
def generate(task_prompt: str, model: str = None, temperature: float = None,
             max_tokens: int = None) -> Iterator[str]:
    """Stream one generated document (course outline, lab guide, quiz…)."""
    messages = [{"role": "system", "content": BASE_SYSTEM},
                {"role": "user", "content": task_prompt}]
    return _stream(messages, model=model,
                   temperature=0.5 if temperature is None else temperature,
                   max_tokens=max_tokens or 3000)


def refine(previous_md: str, instruction: str, model: str = None) -> Iterator[str]:
    """Re-work an existing draft per a quick instruction (shorter/deeper/table…)."""
    user = (
        "Here is a document you produced:\n\n"
        f"{(previous_md or '')[:9000]}\n\n"
        f"{instruction}\n\n"
        "Return the COMPLETE revised document, not a diff or a description of the "
        "changes. Keep the same house style: one '# Title', '## ' section headings, "
        "every list item on its own line, fenced code blocks with a language tag, "
        "and tables where they help."
    )
    messages = [{"role": "system", "content": BASE_SYSTEM},
                {"role": "user", "content": user}]
    return _stream(messages, model=model, temperature=0.5, max_tokens=3000)
