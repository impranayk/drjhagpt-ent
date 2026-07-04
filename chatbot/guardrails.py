"""Lightweight, open-source guardrails — no paid services.

  - Prompt-injection detection (heuristics)
  - PII redaction (regex by default; optional Microsoft Presidio if installed)
  - Optional content moderation via Groq's Llama Guard (open weights, free tier)

All checks fail *open* on internal error so a guardrail bug never takes the app
down — appropriate for a prototype. In production you would fail closed and alert.
"""
import re
from typing import Tuple

from . import config

# --- Prompt-injection heuristics -------------------------------------------
_INJECTION_PATTERNS = [
    r"ignore (all|any|the|previous|above).{0,24}(instructions|prompt|rules)",
    r"disregard (the|all|any|previous|above).{0,24}(instructions|prompt|rules)",
    r"reveal (your|the)\s?(system\s)?(prompt|instructions)",
    r"you are now\b",
    r"pretend to be\b",
    r"\bjailbreak\b",
    r"do anything now|\bDAN\b",
    r"</?(system|assistant|user)>",
]
_INJECTION_RE = [re.compile(p, re.I) for p in _INJECTION_PATTERNS]

# --- PII patterns (regex fallback) -----------------------------------------
_PII_PATTERNS = {
    "EMAIL": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "PHONE": re.compile(r"\b\+?\d[\d\s().-]{7,}\d\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


def check_input(text: str) -> Tuple[bool, str]:
    """Return (allowed, reason). Blocks obvious prompt-injection attempts."""
    if not config.ENABLE_GUARDRAILS:
        return True, ""
    for rx in _INJECTION_RE:
        if rx.search(text or ""):
            return False, ("That request looks like a prompt-injection attempt "
                           "and was blocked. Please rephrase your question.")
    return True, ""


def redact_pii(text: str) -> str:
    """Mask common PII. Uses Presidio if enabled + installed, else regex."""
    if not text or not config.ENABLE_GUARDRAILS:
        return text
    if config.USE_PRESIDIO:
        try:
            return _presidio_redact(text)
        except Exception:
            pass  # fall back to regex
    out = text
    for label, rx in _PII_PATTERNS.items():
        out = rx.sub(f"[{label}]", out)
    return out


def _presidio_redact(text: str) -> str:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine

    global _ANALYZER, _ANON
    try:
        _ANALYZER
    except NameError:
        _ANALYZER = AnalyzerEngine()
        _ANON = AnonymizerEngine()
    results = _ANALYZER.analyze(text=text, language="en")
    return _ANON.anonymize(text=text, analyzer_results=results).text


def moderate(text: str, role: str = "user") -> Tuple[bool, str]:
    """Optional moderation via Groq's Llama Guard (open weights).

    Returns (is_safe, detail). No-op (safe) if disabled or no API key.
    """
    if not (config.ENABLE_GUARDRAILS and config.ENABLE_MODERATION) or not config.GROQ_API_KEY:
        return True, ""
    try:
        from groq import Groq

        client = Groq(api_key=config.GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=config.GUARD_MODEL,
            messages=[{"role": role, "content": text}],
        )
        verdict = (resp.choices[0].message.content or "").strip()
        return verdict.lower().startswith("safe"), verdict
    except Exception:
        return True, ""  # fail open in the prototype
