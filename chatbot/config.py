"""Central configuration for DrJhaGPT Pro — the technical training studio.

Reads settings from environment variables (loaded from a local .env in
development, or from Streamlit secrets when deployed to Streamlit Cloud).
"""
import os
import re
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
LLM_READY = bool(GROQ_API_KEY or LLM_BASE_URL or _get("GEMINI_API_KEY", ""))

# Models offered in the UI picker (comma-separated). Groq open models by default.
AVAILABLE_MODELS = [m.strip() for m in _get(
    "AVAILABLE_MODELS",
    "llama-3.3-70b-versatile,llama-3.1-8b-instant,openai/gpt-oss-120b,"
    "meta-llama/llama-4-scout-17b-16e-instruct,qwen/qwen3-32b",
).split(",") if m.strip()]

# --- Google Gemini (free tier) — a SECOND provider, not a replacement ---
# Groq's free tier has a daily cap. When every Groq key is spent the studio keeps
# working on Gemini instead of failing mid-document. Optional: with no key set,
# behaviour is exactly as before. Get one at https://aistudio.google.com/apikey
GEMINI_API_KEY = _get("GEMINI_API_KEY", "")
GEMINI_MODELS = [m.strip() for m in _get(
    "GEMINI_MODELS", "gemini-2.5-flash,gemini-2.0-flash").split(",") if m.strip()]
GEMINI_READY = bool(GEMINI_API_KEY)
if GEMINI_READY:
    AVAILABLE_MODELS += [m for m in GEMINI_MODELS if m not in AVAILABLE_MODELS]


def is_gemini(model: str) -> bool:
    return (model or "").lower().startswith("gemini")

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
BRAND_STUDIO_EYEBROW = "Studio for Technical Training"
BRAND_TAGLINE = "Ask Dr. Pranay Jha anything — answered from his published work on VMware, Cloud & AI."
WEBSITE_URL = "https://drpranayjha.com"
# Shown as a help CTA when the free daily model quota is used up.
SUPPORT_WHATSAPP = _get("SUPPORT_WHATSAPP", "")        # digits only, incl. country code

# Environment label — set APP_ENV=staging in a staging app's secrets to get a
# clear "test environment" banner and (optionally) a separate database.
APP_ENV = _get("APP_ENV", "production")
IS_STAGING = APP_ENV.lower() not in ("production", "prod", "")

# Brand palette (from the site's CSS custom properties)
COLOR_INK = "#141618"
COLOR_ACCENT = "#ce242c"
COLOR_ACCENT_DARK = "#a81d24"
COLOR_PANEL = "#f5f5f5"
COLOR_MUTED = "#5f5e5a"

# =============================================================================
#  Studio — shared library (Supabase), roles and tracks
# =============================================================================
# Optional: with SUPABASE_URL / SUPABASE_KEY unset the studio still works fully
# for a single trainer — the library, admin console and DB-backed logins simply
# don't appear, and logins fall back to .streamlit/auth.yaml.
SUPABASE_URL = _get("SUPABASE_URL", "")
SUPABASE_KEY = _get("SUPABASE_KEY", "")     # service_role key (server-side secret only)
LIBRARY_ENABLED = bool(SUPABASE_URL and SUPABASE_KEY)

# Pluggable auth backend. "local" = built-in bcrypt logins (DB first, then
# auth.yaml). Set to "sso" later without touching the rest of the app.
AUTH_PROVIDER = _get("AUTH_PROVIDER", "local")

# --- Roles (RBAC) ---
# admin        : full control + the Admin Console (people, tracks, rights)
# lead         : lead trainer — every tool, publishes to ALL tracks
# trainer      : delivers training — every day-to-day tool, publishes to own track
# associate    : assisting/junior — a reduced toolset, reads the shared library
ROLE_ADMIN, ROLE_LEAD, ROLE_TRAINER, ROLE_ASSOCIATE = (
    "admin", "lead", "trainer", "associate")
ALL_ROLES = [ROLE_ADMIN, ROLE_LEAD, ROLE_TRAINER, ROLE_ASSOCIATE]
ROLE_LABELS = {ROLE_ADMIN: "Admin", ROLE_LEAD: "Lead Trainer",
               ROLE_TRAINER: "Trainer", ROLE_ASSOCIATE: "Associate"}
# Usernames always treated as admin, so there is a way in before anyone is set
# up in the database.
ADMIN_USERS = [u.strip().lower() for u in _get("ADMIN_USERS", "pranay").split(",")
               if u.strip()]

# Tools only a lead trainer / admin may open — these set the shared agenda.
LEAD_ONLY_TOOLS = ["course", "studyplan"]
# Tools an associate may not open (they assist; they don't author the syllabus).
ASSOCIATE_BLOCKED_TOOLS = ["course", "studyplan", "article"]
# Models an associate / trainer may pick (leads and admins get all). Keeps output
# consistent and daily quota predictable. Per-user `allowed_models` wins.
TRAINER_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

# --- Tracks (the practice a trainer belongs to; the unit material is shared to) -
# One per line (or semicolon-separated); "CODE = Friendly Name" keeps a stable
# code while the display name can change. Example (TOML triple-quoted):
#     TRACKS = """
#     VMW = VMware & Private Cloud
#     CLD = Public Cloud & Kubernetes
#     """
def _parse_tracks(raw: str):
    codes, labels = [], {}
    for item in re.split(r"[;\n]+", raw or ""):
        item = item.strip()
        if not item:
            continue
        code, label = ((p.strip() for p in item.split("=", 1))
                       if "=" in item else (item, item))
        codes.append(code)
        labels[code] = label or code
    return codes, labels


TRACKS, TRACK_LABELS = _parse_tracks(_get(
    "TRACKS",
    "VMW = VMware & Private Cloud\n"
    "CLD = Public Cloud\n"
    "K8S = Kubernetes & Containers\n"
    "AUT = Automation & DevOps\n"
    "AIX = AI Infrastructure",
))
DEFAULT_TRACK = TRACKS[0] if TRACKS else "VMW"


def track_label(code: str) -> str:
    """Friendly display name for a track code ('all' → 'All tracks')."""
    if code == "all":
        return "All tracks"
    return TRACK_LABELS.get(code, code)


# --- Website bridge (optional) ---
# Lets a lead ALSO post an article/announcement to drpranayjha.com from the same
# Publish step — opt-in per publish, as a draft by default. Unset = hidden.
WEBSITE_POST_URL = _get("WEBSITE_POST_URL", "")
WEBSITE_POST_TOKEN = _get("WEBSITE_POST_TOKEN", "")
WEBSITE_POST_READY = bool(WEBSITE_POST_URL and WEBSITE_POST_TOKEN)

# =============================================================================
#  Domain vocabulary — the fields every generator form is built from
# =============================================================================
# Technology areas Dr Jha trains on. The free-text "Topic" field always wins;
# this list is for fast selection and for steering the model's vocabulary.
TECH_AREAS = [
    "VMware vSphere",
    "VMware Cloud Foundation (VCF)",
    "VMware vSAN",
    "VMware NSX",
    "VMware Aria / VCF Operations",
    "VMware HCX / Migration",
    "VMware Tanzu / vSphere Kubernetes Service",
    "VMware Site Recovery / DR",
    "AWS", "Microsoft Azure", "Google Cloud", "Oracle Cloud (OCI)",
    "Kubernetes", "OpenShift", "Docker & Containers",
    "Linux / RHEL", "Windows Server",
    "Networking", "Storage (SAN / NAS)",
    "Terraform", "Ansible", "PowerCLI / PowerShell", "Python for Infra",
    "CI/CD & GitOps",
    "AI Infrastructure & GPU sizing", "Private AI / RAG platforms",
    "Security & Hardening", "Backup, BCDR & Resilience",
    "Other / mixed",
]

# Audience depth, using the industry-standard L100–L400 shorthand.
AUDIENCE_LEVELS = [
    "L100 — Awareness / introduction",
    "L200 — Practitioner / hands-on",
    "L300 — Advanced / deep dive",
    "L400 — Expert / architect",
]
AUDIENCE_ROLES = [
    "Freshers / students", "System administrators", "Cloud & infra engineers",
    "Solution architects", "SRE / DevOps engineers", "Support / operations",
    "Pre-sales & consultants", "Managers / decision makers", "Mixed audience",
]
DELIVERY_MODES = [
    "Instructor-led (in person)", "Virtual instructor-led (VILT)",
    "Hands-on workshop", "Self-paced", "Webinar / conference talk",
    "Bootcamp", "1:1 mentoring",
]
SESSION_LENGTHS = ["30 minutes", "45 minutes", "1 hour", "90 minutes", "2 hours",
                   "3 hours", "Half day (4 hours)", "Full day (7 hours)"]
COURSE_LENGTHS = ["1 day", "2 days", "3 days", "4 days", "5 days",
                  "2 weeks", "4 weeks", "8 weeks", "12 weeks"]

# Scripting / IaC languages the Script Studio and Code Explainer cover.
SCRIPT_LANGUAGES = [
    "PowerCLI", "PowerShell", "Bash / Shell", "Python",
    "Ansible (YAML)", "Terraform (HCL)", "Kubernetes YAML", "Helm",
    "REST / curl", "Go", "SQL", "YAML / JSON (config)", "Other",
]

# Certification tracks for the Quiz Builder and Study Plan.
CERTIFICATIONS = [
    "— not exam-specific —",
    "VMware VCP-DCV", "VMware VCP-VCF", "VMware VCAP-DCV Design",
    "VMware VCAP-DCV Deploy", "VMware VCF Administrator", "VMware NSX Professional",
    "AWS Solutions Architect Associate", "AWS Solutions Architect Professional",
    "AWS SysOps Administrator",
    "Azure AZ-104 Administrator", "Azure AZ-305 Architect", "Azure AZ-700 Networking",
    "Google Associate Cloud Engineer", "Google Professional Cloud Architect",
    "CKA — Certified Kubernetes Administrator", "CKAD", "CKS",
    "RHCSA", "RHCE", "HashiCorp Terraform Associate", "Other / custom",
]

# Question styles the Quiz Builder can produce. (label, needs_item_count)
QUIZ_FORMATS = [
    ("Multiple choice — single answer", True),
    ("Multiple choice — multi-select", True),
    ("True / False", True),
    ("Scenario / case-based", True),
    ("Command & output based", True),
    ("Fill in the blank", True),
    ("Match the following", True),
    ("Short answer (viva style)", True),
    ("Whiteboard / design question", True),
]
QUIZ_COUNTS = ["5", "10", "15", "20", "25", "30", "50", "Custom…"]

# Diagram styles the Architecture Diagram tool renders (via Mermaid).
DIAGRAM_TYPES = [
    "Architecture / components", "Network topology", "Deployment topology",
    "Sequence / call flow", "Decision flowchart", "State machine",
    "Migration phases / timeline", "Data model / entities", "Mind map",
]

# Cheat-sheet and runbook flavours.
DOC_TONES = ["Practical & concise", "Deep & thorough", "Exam-focused",
             "Executive / business-friendly", "Storytelling / analogy-led"]

# Common lab environment presets, so a lab guide states its assumptions.
LAB_ENVIRONMENTS = [
    "Nested lab (VMware Workstation / ESXi)", "Home lab (physical)",
    "Hands-on Labs (VMware HOL)", "Cloud free tier / sandbox",
    "Customer / production-like environment", "Local machine (Docker / minikube)",
    "Instructor-provided lab pods", "Not specified",
]
