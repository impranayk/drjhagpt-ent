"""Central configuration for the Dr. Pranay Jha AI Assistant.

Reads settings from environment variables (loaded from a local .env in
development, or from Streamlit secrets when deployed to Streamlit Cloud).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load a local .env if present (no-op in production where env vars are set).
load_dotenv()

# --- Paths ---
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
ASSETS_DIR = ROOT_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"
EMBEDDINGS_PATH = DATA_DIR / "knowledge.npz"      # numpy vectors
CHUNKS_PATH = DATA_DIR / "chunks.json"            # text + metadata


def _get(name: str, default: str = "") -> str:
    """Read a setting from env first, then Streamlit secrets if available."""
    value = os.getenv(name)
    if value:
        return value
    try:  # Streamlit secrets are optional and only exist when deployed.
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return default


# --- LLM (Groq by default; self-hosted OpenAI-compatible for on-prem / air-gap) ---
GROQ_API_KEY = _get("GROQ_API_KEY")        # one key, or several comma-separated
GROQ_API_KEY2 = _get("GROQ_API_KEY2", "")  # optional 2nd-account key for failover
GROQ_MODEL = _get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Provider: "groq" (default) or "openai" (any OpenAI-compatible endpoint:
# vLLM / Ollama / NVIDIA NIM). Setting LLM_BASE_URL also selects the openai path.
LLM_PROVIDER = _get("LLM_PROVIDER", "groq")
LLM_BASE_URL = _get("LLM_BASE_URL", "")        # e.g. http://vllm:8000/v1
LLM_API_KEY = _get("LLM_API_KEY", "")          # token for the self-hosted endpoint (if any)
LLM_MODEL = _get("LLM_MODEL", GROQ_MODEL)      # model name for the chosen provider
LLM_READY = bool(GROQ_API_KEY or LLM_BASE_URL)

# Models offered in the UI picker (comma-separated). Groq open models by default.
AVAILABLE_MODELS = [m.strip() for m in _get(
    "AVAILABLE_MODELS",
    "llama-3.3-70b-versatile,llama-3.1-8b-instant,openai/gpt-oss-120b,"
    "meta-llama/llama-4-scout-17b-16e-instruct,qwen/qwen3-32b",
).split(",") if m.strip()]

# --- Retrieval / RAG ---
EMBED_MODEL = _get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
RAG_TOP_K = int(_get("RAG_TOP_K", "4"))
RAG_MIN_SCORE = float(_get("RAG_MIN_SCORE", "0.30"))

# --- Phase 1: hybrid retrieval + reranking ---
# mode: "dense" (vectors only) | "hybrid" (dense + BM25 via RRF) | "hybrid_rerank"
# Default is "hybrid": on this small, clean corpus the eval shows dense is already
# saturated (100% hit@5) and a generic reranker slightly hurt — so rerank is
# available but OFF by default until validated on a representative eval set with a
# domain-appropriate reranker. Run `python eval/run_eval.py` to compare modes.
RETRIEVAL_MODE = _get("RETRIEVAL_MODE", "hybrid")
RETRIEVE_CANDIDATES = int(_get("RETRIEVE_CANDIDATES", "40"))  # candidates before rerank
RRF_K = int(_get("RRF_K", "60"))                             # reciprocal-rank-fusion constant
RERANK_MODEL = _get("RERANK_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2")
VECTOR_BACKEND = _get("VECTOR_BACKEND", "numpy")   # "numpy" (default) | "qdrant" (local, embedded)

# --- Phase 2: auth, guardrails, observability (all open-source, no license) ---
AUTH_CONFIG_PATH = ROOT_DIR / ".streamlit" / "auth.yaml"
ENABLE_AUTH = _get("ENABLE_AUTH", "1") == "1"
ENABLE_GUARDRAILS = _get("ENABLE_GUARDRAILS", "1") == "1"
ENABLE_TRACING = _get("ENABLE_TRACING", "1") == "1"
ENABLE_MODERATION = _get("ENABLE_MODERATION", "0") == "1"   # Groq Llama Guard (extra call)
GUARD_MODEL = _get("GUARD_MODEL", "llama-guard-3-8b")
USE_PRESIDIO = _get("USE_PRESIDIO", "0") == "1"             # production-grade PII engine
LOGS_DIR = ROOT_DIR / "logs"
TRACE_PATH = LOGS_DIR / "traces.jsonl"
FEEDBACK_PATH = LOGS_DIR / "feedback.jsonl"

# --- Branding (matched to drpranayjha.com) ---
BRAND_NAME = "DrJhaGPT"
BRAND_EDITION = "Pro"                                  # production-hardened edition
BRAND_FULL = f"{BRAND_NAME} {BRAND_EDITION}"           # "DrJhaGPT Pro"
BRAND_EYEBROW = "Journal of Intelligent Infrastructure"
BRAND_TAGLINE = "Ask Dr. Pranay Jha anything — answered from his published work on VMware, Cloud & AI."
WEBSITE_URL = "https://drpranayjha.com"

# Brand palette (from the site's CSS custom properties)
COLOR_INK = "#141618"
COLOR_ACCENT = "#ce242c"
COLOR_ACCENT_DARK = "#a81d24"
COLOR_PANEL = "#f5f5f5"
COLOR_MUTED = "#5f5e5a"
