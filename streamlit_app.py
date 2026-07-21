"""DrJhaGPT Pro — a technical-training studio with a brand-matched editorial UI.

A task studio for building and delivering training on VMware, cloud, Kubernetes,
automation and AI infrastructure: course outlines, session plans, labs, demos,
assessments, scripts, runbooks and handouts — plus the grounded RAG chat the app
started life as, which now lives as the "Ask" tool.

Stack: Groq / Gemini (open LLMs) for generation, hybrid retrieval over
drpranayjha.com and uploaded PDFs for grounding, optional Supabase for the shared
library and multi-trainer access.

Visual design mirrors drpranayjha.com: white editorial theme, Inter/Oswald type,
charcoal ink (#141618) with a red accent (#ce242c).
"""
import base64
import datetime as _dt
import html
import re
from functools import lru_cache

import streamlit as st

from chatbot import (admin, auth, config, documents, feedback, guardrails, llm,
                     observability, rag, render, retrieval, store, studio, tools)

# Shown in the sidebar footer. BUMP THIS ON EVERY CHANGE - it is the only way to
# tell from the browser whether Streamlit Cloud has actually picked up a push.
APP_VERSION = "1.2.0"


# ----------------------------------------------------------------------------- assets
@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    if not config.LOGO_PATH.exists():
        return ""
    b64 = base64.b64encode(config.LOGO_PATH.read_bytes()).decode()
    return f"data:image/png;base64,{b64}"


@lru_cache(maxsize=1)
def logo_image():
    """PIL image for the page icon and assistant avatar (falls back to emoji)."""
    try:
        from PIL import Image

        return Image.open(config.LOGO_PATH)
    except Exception:
        return "🤖"


SUGGESTIONS = [
    "What is VMware HCX and when should I use it?",
    "Give me a VCF 9 pre-installation checklist",
    "How do I size infrastructure for an AI workload?",
    "vSphere HA vs DRS — what's the difference?",
]

st.set_page_config(
    page_title=config.BRAND_FULL,
    page_icon=logo_image(),
    layout="centered",
    initial_sidebar_state="auto",
)

# ----------------------------------------------------------------------------- styling
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Oswald:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --ink: #141618; --accent: #ce242c; --accent-dark: #a81d24;
  --muted: #5f5e5a; --panel: #f5f5f5; --border: #e7e7e7;
}

/* Base type + background */
html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif; color: var(--ink); }
.stApp { background: #ffffff; }

/* Hide Streamlit chrome + the Community Cloud "Built with Streamlit" badge */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="stAppViewerBadge"],
[data-testid="stAppDeployButton"],
[class*="viewerBadge"], [class*="_viewerBadge"], [class*="ViewerBadge"],
[class*="_profileContainer"], [class*="profileContainer"], [data-testid="InputInstructions"],
[data-testid="manageAppButton"], [data-testid="stAppToolbar"],
a[href*="streamlit.io"], a[href*="streamlit.app"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent; height: 0; }
/* The sidebar-expand control lives inside that zero-height header, so it became
   unreachable - which strands you on mobile (where the sidebar auto-collapses)
   with no way to reach the tool list. Pin it to the viewport instead. */
[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {
  position: fixed !important; top: 8px; left: 8px; z-index: 1000;
  background: #fff !important; border: 1px solid var(--border) !important;
  border-radius: 6px !important; box-shadow: 0 2px 8px rgba(20,22,24,.10); }
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="collapsedControl"] svg { color: var(--accent) !important; }
.st-key-new_chat { margin-top: 6px; }

/* Embedded mode: the same panel, moved into the main column. */
.st-key-dj_menu { margin-bottom: 10px; }
.st-key-dj_menu [data-testid="stExpander"] details { border: 1px solid var(--border);
  border-radius: 8px; background: #fff; }
.st-key-dj_menu [data-testid="stExpander"] summary { font-family: 'Oswald', sans-serif;
  font-size: 12px; letter-spacing: 1.4px; text-transform: uppercase; color: var(--accent); }
.st-key-dj_menu div[data-testid="stButton"] button { border-radius: 6px !important;
  text-align: left !important; padding: 6px 11px !important; font-size: 13px !important;
  border-color: transparent !important; }
.st-key-dj_menu div[data-testid="stButton"] button:hover {
  background: var(--panel) !important; border-color: var(--border) !important; }

.block-container { max-width: 860px; padding-top: 1.6rem; padding-bottom: 6rem; }

/* ---- Masthead ---- */
.dj-masthead { display: flex; align-items: center; gap: clamp(10px, 3vw, 18px); }
.dj-masthead img { width: clamp(44px, 13vw, 60px); height: clamp(44px, 13vw, 60px);
                   border-radius: 12px; border: 2px solid var(--accent);
                   box-shadow: 0 1px 4px rgba(0,0,0,.10); flex-shrink: 0; }
.dj-headtext { display: flex; flex-direction: column; min-width: 0; }
.dj-title { font-family: 'Oswald', sans-serif !important; color: var(--ink);
            font-size: clamp(22px, 6.5vw, 32px);
            font-weight: 700; letter-spacing: .3px; line-height: .95 !important;
            margin: 0 !important; padding: 0 !important; white-space: nowrap; }
.dj-title .accent { color: var(--accent); }
.dj-pro { font-family: 'Inter', sans-serif; font-size: 10px; font-weight: 700; letter-spacing: 1px;
          color: #fff; background: var(--accent); padding: 2px 6px; border-radius: 6px;
          vertical-align: middle; margin-left: 8px; position: relative; top: -3px; }
.dj-journal { font-family: 'Inter', sans-serif; font-style: italic; color: var(--accent);
              font-size: clamp(10px, 3vw, 11px); font-weight: 500; letter-spacing: .2px;
              line-height: 1.2; margin: 4px 0 0 !important; padding: 0 !important;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dj-rule { height: 1.5px; background: var(--accent); width: 100%; border: 0; margin: 14px 0 6px;
           border-radius: 0; }

/* Frozen (sticky) header while content scrolls under it.
   !important is required: Streamlit sets position:relative on the block wrapper
   with equal specificity, so without it our sticky is overridden. */
.st-key-dj_header,
[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-dj_header) {
  position: sticky !important; top: 0 !important; z-index: 100;
  background: #ffffff; padding-top: .4rem;
}

/* ---- Login card ---- */
.st-key-dj_login_card { max-width: 430px; margin: 5vh auto 0; background: #ffffff;
  border: 1px solid var(--border); border-radius: 16px; padding: 30px 30px 22px;
  box-shadow: 0 12px 34px rgba(20,22,24,.07); }
.dj-login-head { display: flex; align-items: center; gap: 14px; }
.dj-login-logo { width: 46px; height: 46px; border-radius: 11px; border: 2px solid var(--accent);
  box-shadow: 0 1px 4px rgba(0,0,0,.10); }
.dj-login-word { font-family: 'Oswald', sans-serif; font-weight: 700; font-size: 26px;
  letter-spacing: .3px; line-height: 1; color: var(--ink); }
.dj-login-word .accent { color: var(--accent); }
.dj-login-pro { font-family: 'Inter', sans-serif; font-size: 10px; font-weight: 700; letter-spacing: 1px;
  color: #fff; background: var(--accent); padding: 2px 6px; border-radius: 6px; margin-left: 6px;
  position: relative; top: -3px; }
.dj-login-eyebrow { font-family: 'Inter', sans-serif; font-style: italic; color: var(--accent);
  font-size: 11px; font-weight: 500; margin-top: 5px; }
.dj-login-rule { height: 1.5px; background: var(--accent); border: 0; margin: 18px 0 14px; }
.dj-login-title { font-family: 'Oswald', sans-serif; font-size: 19px; font-weight: 600; color: var(--ink);
  letter-spacing: .2px; }
.dj-login-sub { color: var(--muted); font-size: 13px; margin: 3px 0 2px; }
.dj-login-foot { color: var(--muted); font-size: 12px; text-align: center; margin-top: 16px; }
.dj-login-foot a { color: var(--accent); text-decoration: none; }
.st-key-dj_login_card [data-testid="stForm"] { border: 0 !important; padding: 0 !important; }
.st-key-dj_login_card [data-baseweb="input"] { border-radius: 9px !important; }
.st-key-dj_login_card [data-testid="stForm"] button {
  background: var(--accent) !important; color: #fff !important; border: 0 !important;
  border-radius: 9px !important; font-weight: 600 !important; letter-spacing: .2px; padding: .55rem 1rem !important; }
.st-key-dj_login_card [data-testid="stForm"] button:hover { background: var(--accent-dark) !important; }

@media (max-width: 640px) {
  .st-key-dj_header { padding-top: .15rem; }
  .dj-masthead { gap: 10px; }
  .dj-masthead img { width: 34px !important; height: 34px !important; border-radius: 9px; }
  .dj-title { font-size: 20px; }
  .dj-journal { display: none; }
  .dj-rule { margin: 7px 0 3px; }
}

/* ---- Chat messages ---- */
[data-testid="stChatMessage"] { background: transparent; padding: .35rem 0; }
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li { font-size: 15.5px; line-height: 1.7; }
[data-testid="stChatMessage"] a { color: var(--accent); text-decoration: none; border-bottom: 1px solid rgba(206,36,44,.35); }
[data-testid="stChatMessage"] a:hover { border-bottom-color: var(--accent); }
[data-testid="stChatMessage"] h1, [data-testid="stChatMessage"] h2, [data-testid="stChatMessage"] h3 {
  font-family: 'Oswald', sans-serif; color: var(--ink); letter-spacing: .2px; margin-top: .4rem; }
[data-testid="stChatMessage"] code { font-family: 'JetBrains Mono', Consolas, monospace;
  background: var(--panel); border: 1px solid var(--border); border-radius: 3px;
  padding: 1px 5px; font-size: 13px; color: #8a1b21; }
[data-testid="stChatMessage"] pre code { background: #1b1e21; color: #e6e6e6; border: 0; }

/* ---- User question bubble ---- */
.dj-user-row { display: flex; justify-content: flex-end; margin: 12px 0 4px; }
.dj-user-bubble { background: var(--panel); color: var(--ink); border: 1px solid var(--border);
  border-right: 3px solid var(--accent);
  border-radius: 14px 14px 4px 14px; padding: 9px 14px 9px 16px; max-width: 82%;
  font-size: 15px; line-height: 1.55; white-space: pre-wrap; }

/* ---- Source cards ---- */
.dj-sources { margin: 14px 0 2px; }
.dj-sources-label { font-family: 'Oswald', sans-serif; color: var(--accent); font-size: 11px;
                    letter-spacing: 2.5px; font-weight: 600; text-transform: uppercase; margin-bottom: 8px; }
.dj-source { display: flex; flex-direction: column; gap: 2px; text-decoration: none !important;
             border: 1px solid var(--border); border-left: 3px solid var(--accent);
             border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; background: #fff;
             transition: background .15s, box-shadow .15s, transform .15s; }
.dj-source:hover { background: var(--panel); box-shadow: 0 2px 10px rgba(20,22,24,.06); transform: translateY(-1px); }
.dj-source-title { color: var(--ink) !important; font-weight: 600; font-size: 14px; }
.dj-source-host { color: var(--muted); font-size: 12px; }

/* ---- Buttons ---- */
.dj-intro { color: var(--muted); font-size: 14.5px; margin: 6px 0 14px; }
div[data-testid="stButton"] button {
  border: 1px solid var(--border); background: #fff; color: var(--ink);
  border-radius: 999px; padding: 8px 16px; font-size: 13.5px; font-weight: 500;
  text-align: left; transition: all .15s; }
div[data-testid="stButton"] button:hover {
  border-color: var(--accent); color: var(--accent); background: #fff; }
.st-key-new_chat button { border: 1.5px solid var(--accent) !important;
  color: var(--accent) !important; text-align: center !important; }
.st-key-new_chat button:hover { background: var(--accent) !important; color: #fff !important; }

/* Primary form submit buttons read as the main action on every tool. */
[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
  background: var(--accent) !important; color: #fff !important; border: 0 !important;
  border-radius: 8px !important; font-weight: 600 !important; text-align: center !important;
  padding: .55rem 1rem !important; }
[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
  background: var(--accent-dark) !important; }
[data-testid="stForm"] { border: 1px solid var(--border) !important; border-radius: 12px !important;
  padding: 18px 18px 6px !important; background: #fff; }

/* ---- Chat input ---- */
[data-testid="stChatInput"] { border: 1.5px solid var(--accent) !important;
  border-radius: 12px !important; background: #fff !important; }
[data-testid="stChatInput"] > div { border: 0 !important; background: transparent !important; }
[data-testid="stChatInput"]:focus-within { box-shadow: 0 0 0 3px rgba(206,36,44,.15) !important; }
[data-testid="stChatInputSubmitButton"] { background: var(--accent) !important;
  border-radius: 8px !important; }
[data-testid="stChatInputSubmitButton"]:hover { background: var(--accent-dark) !important; }
[data-testid="stChatInputSubmitButton"] svg { color: #fff !important; fill: #fff !important; }

/* ---- Sidebar ---- */
[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
.dj-sb-brand { display: flex; align-items: center; gap: 10px; }
.dj-sb-brand img { width: 36px; height: 36px; border-radius: 8px; border: 2px solid var(--accent); }
.dj-sb-title { font-family: 'Oswald', sans-serif; font-weight: 700; font-size: 21px; color: var(--ink); line-height: 1; }
.dj-sb-title span { color: var(--accent); }
.dj-sb-sub { font-family: 'Inter', sans-serif; font-style: italic; color: var(--accent); font-size: 10.5px; margin-top: 2px; }
.dj-sb-rule { height: 2px; background: var(--accent); border: 0; margin: 10px 0 12px; width: 100%; }
.dj-sb-sep { height: 1px; background: var(--border); border: 0; margin: 22px 0 0; width: 100%; }
/* Sidebar labels sit in their own element container; give the separator the
   same treatment so it isn't swallowed by the block above it. */
[data-testid="stSidebar"] .stElementContainer:has(.dj-sb-sep) { margin: 10px 0 0 !important; }
/* Section labels.
   Spacing MUST go on the element container, not on the label itself. Streamlit
   sizes an element's container from the text's line box and ignores any padding
   or margin on the content, so spacing set here overflows the container and the
   next button paints over the bottom half of the text - which reads as the label
   being chopped in half. Measured: a 31px label sat in a 15px container, so it
   ran 16px into the button below it. The :has() rules further down move the
   spacing to the container, where it is actually accounted for. */
.dj-sb-label { font-family: 'Oswald', sans-serif; color: var(--accent); font-size: 10.5px;
  letter-spacing: 2px; font-weight: 600; text-transform: uppercase;
  margin: 0; padding: 0; line-height: 1.6; }
.dj-sb-group { font-family: 'Oswald', sans-serif; color: var(--muted); font-size: 9.5px;
  letter-spacing: 1.8px; font-weight: 600; text-transform: uppercase;
  margin: 0; padding: 0 2px; line-height: 1.6; }
[data-testid="stSidebar"] .stElementContainer:has(.dj-sb-label),
.st-key-dj_menu .stElementContainer:has(.dj-sb-label) { margin: 20px 0 19px !important; }
[data-testid="stSidebar"] .stElementContainer:has(.dj-sb-group),
.st-key-dj_menu .stElementContainer:has(.dj-sb-group) { margin: 15px 0 18px !important; }
/* First label in the panel shouldn't push the whole list down. */
[data-testid="stSidebar"] .stElementContainer:has(.dj-sb-label):first-of-type {
  margin-top: 8px !important; }
.dj-sb-user { display: flex; align-items: center; gap: 8px; background: var(--panel); border: 1px solid var(--border);
  border-left: 3px solid var(--accent); border-radius: 8px; padding: 8px 11px; margin-bottom: 8px; font-size: 13px; color: var(--ink); }
.dj-sb-user b { font-weight: 700; }
.dj-sb-ava { width: 24px; height: 24px; border-radius: 50%; background: var(--ink); color: #fff;
  display: inline-flex; align-items: center; justify-content: center; font-size: 10px;
  font-weight: 700; letter-spacing: .3px; flex: 0 0 auto; }
.dj-sb-user b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dj-sb-badge { background: var(--accent); color: #fff; font-size: 9px; font-weight: 600; letter-spacing: .5px;
  text-transform: uppercase; padding: 2px 8px; border-radius: 999px; margin-left: auto; }
.dj-sb-status { font-size: 12px; color: var(--muted); line-height: 1.9; }
.dj-sb-status b { color: var(--ink); font-weight: 600; }
.dj-sb-status a { color: var(--accent); text-decoration: none; }
.dj-sb-ver { color: #9a9a9a; font-size: 10px; letter-spacing: .4px; margin-top: 18px; text-align: center; }

/* Navigation buttons: flat, left-aligned, tightly stacked, one click each.
   DESCENDANT combinators, not "> button", on purpose: Streamlit versions differ
   in whether a wrapper div sits between [data-testid="stButton"] and the button
   element. A child combinator silently matched nothing on Streamlit Cloud while
   working locally, which is why the labels stayed centred there.
   Streamlit buttons are flex containers, so text-align alone does nothing - the
   label is centred by justify-content, and every level that could carry that
   centring is pinned below. */
[data-testid="stSidebar"] div[data-testid="stButton"] button,
.st-key-dj_menu div[data-testid="stButton"] button {
  justify-content: flex-start !important; text-align: left !important;
  border-radius: 6px !important; padding: 5px 11px !important; min-height: 0 !important;
  font-size: 13px !important; font-weight: 500 !important;
  border-color: transparent !important; width: 100%; }
[data-testid="stSidebar"] div[data-testid="stButton"] button *,
.st-key-dj_menu div[data-testid="stButton"] button * {
  justify-content: flex-start !important; text-align: left !important;
  width: 100%; margin-right: auto; }
[data-testid="stSidebar"] div[data-testid="stButton"] button:hover,
.st-key-dj_menu div[data-testid="stButton"] button:hover {
  background: var(--panel) !important; border-color: var(--border) !important;
  color: var(--accent) !important; }
/* The selected tool. Streamlit's own "primary" type carries the state, so no
   per-button container is needed - those containers were what created the big
   vertical gaps, one block gap per tool. */
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"],
.st-key-dj_menu [data-testid="stBaseButton-primary"] {
  background: var(--ink) !important; color: #fff !important;
  border-color: var(--ink) !important; font-weight: 600 !important; }
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover,
.st-key-dj_menu [data-testid="stBaseButton-primary"]:hover {
  background: #000 !important; color: #fff !important; }
/* Tighten the stack: the default 1rem block gap between 18 tools is enormous. */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"],
.st-key-dj_menu [data-testid="stVerticalBlock"] { gap: 0.18rem !important; }
[data-testid="stSidebar"] div[data-testid="stDownloadButton"] button {
  justify-content: center !important; text-align: center !important;
  border-radius: 8px !important; }

[data-testid="stFileUploaderDropzone"] { border: 1.5px dashed var(--accent) !important;
  background: #fff !important; border-radius: 10px !important; }
[data-baseweb="select"] > div:focus-within { border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px rgba(206,36,44,.12) !important; }

/* ---- Studio: tool page furniture ---- */
.dj-tool-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 2px; }
.dj-tool-name { font-family: 'Oswald', sans-serif; font-size: 22px; font-weight: 600;
  text-transform: uppercase; letter-spacing: .5px; color: var(--ink); }
.dj-tool-group { font-family: 'Oswald', sans-serif; font-size: 10px; letter-spacing: 2px;
  text-transform: uppercase; color: #fff; background: var(--accent); padding: 3px 8px; border-radius: 3px; }
.dj-tool-blurb { color: var(--muted); font-size: 14px; margin: 4px 0 16px; }
.dj-refine-label { font-family: 'Oswald', sans-serif; color: var(--accent); font-size: 10.5px;
  letter-spacing: 2.2px; font-weight: 600; text-transform: uppercase; margin: 20px 0 6px; }
.dj-share { display: flex; align-items: center; gap: 10px; margin: 14px 0 4px; }
.dj-share-lbl { font-family: 'Oswald', sans-serif; color: var(--muted); font-size: 10px;
  letter-spacing: 2px; text-transform: uppercase; }
.dj-share-a { color: var(--accent) !important; text-decoration: none !important; font-size: 13px;
  font-weight: 500; border: 1px solid var(--border); border-radius: 999px; padding: 4px 13px; }
.dj-share-a:hover { border-color: var(--accent); }
.dj-limit { border: 1px solid var(--border); border-left: 3px solid var(--accent);
  border-radius: 8px; padding: 14px 16px; background: var(--panel); font-size: 14px;
  line-height: 1.65; color: var(--ink); }
.dj-limit a { color: var(--accent); }
.dj-env { background: #fff4e5; border: 1px solid #f0c98a; border-radius: 6px; padding: 7px 12px;
  font-size: 12.5px; color: #7a5300; margin-bottom: 12px; }

/* ---- Chips + people/track lists (Admin, Library) ---- */
.dj-chip { display: inline-block; font-size: 10.5px; font-weight: 600; letter-spacing: .4px;
  padding: 2px 9px; border-radius: 999px; margin-left: 6px; border: 1px solid var(--border);
  color: var(--muted); background: #fff; }
.dj-chip-a { background: var(--ink); color: #fff; border-color: var(--ink); }
.dj-chip-l { background: var(--accent); color: #fff; border-color: var(--accent); }
.dj-chip-t { background: var(--panel); color: var(--ink); }
.dj-chip-s { background: #e9f6ee; color: #15703f; border-color: #bfe3ce; }
.dj-chip-d { background: #fbeaea; color: #9b1c22; border-color: #f0c4c6; }
.dj-people { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin-bottom: 14px; }
.dj-person { display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 10px 14px; border-bottom: 1px solid var(--border); font-size: 13.5px; }
.dj-person:last-child { border-bottom: 0; }
.dj-person-u { color: var(--muted); font-size: 12px; margin-left: 8px; }

/* Tabs (Admin Console) */
[data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border); }
[data-baseweb="tab"] { font-family: 'Oswald', sans-serif; font-size: 12px; letter-spacing: 1.2px;
  text-transform: uppercase; }
[data-baseweb="tab"][aria-selected="true"] { color: var(--accent) !important; }
[data-baseweb="tab-highlight"] { background: var(--accent) !important; }
</style>
""",
    unsafe_allow_html=True,
)

# The generated-document styles. Without these the in-app document is raw HTML:
# the header logo renders at natural size, every section icon fills the column
# width as a huge black glyph, and the Course/Trainer/Date row runs together.
# They were previously only injected into the print frame and the download file.
st.markdown(f"<style>{render.DOC_CSS}</style>", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- chrome
def clear_chat():
    st.session_state.messages = []
    st.session_state.pop("pending", None)


def goto(tool_key):
    """Navigate to a tool (used as a button callback, so it lands before rerun)."""
    st.session_state["tool"] = tool_key


def render_header():
    with st.container(key="dj_header"):
        if "mini" in st.query_params:
            # Compact header for the floating widget (its own bar shows the brand).
            _, right = st.columns([2, 1])
            with right:
                st.button("↺  New chat", key="new_chat", on_click=clear_chat,
                          use_container_width=True)
            return
        logo = logo_data_uri()
        img = f'<img src="{logo}" alt="logo">' if logo else ""
        st.markdown(
            f"""
            <div class="dj-masthead">
              {img}
              <div class="dj-headtext">
                <h1 class="dj-title">DrJha<span class="accent">GPT</span><span class="dj-pro">PRO</span></h1>
                <p class="dj-journal">{config.BRAND_STUDIO_EYEBROW}</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<hr class="dj-rule">', unsafe_allow_html=True)


def _model_label(m: str) -> str:
    """Friendly names, so the picker reads as capability rather than model ids."""
    friendly = {
        "llama-3.3-70b-versatile": "Standard — best all-round",
        "llama-3.1-8b-instant": "Quick — fastest, lighter depth",
        "openai/gpt-oss-120b": "Deep — longest, most thorough",
        "meta-llama/llama-4-scout-17b-16e-instruct": "Wide — long documents",
        "qwen/qwen3-32b": "Precise — good with code",
    }
    if config.is_gemini(m):
        return f"Google {m.replace('gemini-', 'Gemini ').replace('-', ' ')}"
    return friendly.get(m, m)


def menu_in_main() -> bool:
    """True when the navigation panel must be drawn in the main column.

    Background, because this cost a live outage: `?embed=true` does not merely
    collapse the sidebar - Streamlit never renders it, and renders no expand
    control either. The whole studio navigation lives in the sidebar, so an
    embedded app shows a chat box and nothing else.

    It cannot be auto-detected: Streamlit's frontend CONSUMES `embed` and
    `embed_options`, so they never reach `st.query_params`. The fix is therefore
    to embed WITHOUT `embed=true` (the app's own CSS already hides the toolbar,
    badge and deploy button, so it looks the same and the sidebar works).

    `?menu=main` is the escape hatch: it forces the panel into the main column
    for any host that must use embed mode. `mini` is the chat-only widget and
    deliberately gets no menu.
    """
    try:
        return (st.query_params.get("menu") == "main"
                and "mini" not in st.query_params)
    except Exception:
        return False


_TITLES = {"dr", "mr", "mrs", "ms", "prof", "er", "shri", "smt"}


def _initials(name: str) -> str:
    """Initials for the user chip, ignoring honorifics.

    "Dr. Pranay Jha" should read PJ, not D.
    """
    parts = [p for p in re.split(r"[\s.]+", name or "")
             if p and p.lower() not in _TITLES]
    if not parts:
        return (name or "?").strip()[:1].upper() or "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][:1] + parts[-1][:1]).upper()


def _elide(text: str, limit: int) -> str:
    """Shorten to `limit`, breaking on a word so labels don't end mid-syllable."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    if " " in cut[limit // 2:]:
        cut = cut[:cut.rfind(" ")].rstrip()
    return cut.rstrip(" -–—·,;:") + "…"


def _nav_button(key, current):
    """One tool in the navigation list.

    Deliberately NOT wrapped in st.container: a container per tool adds one
    vertical block gap each, which stretched the 18-tool list down the page.
    Streamlit's own primary/secondary type carries the selected state instead.
    """
    st.button(studio.TOOL_LABELS[key], key=f"navb_{key}", on_click=goto,
              args=(key,), use_container_width=True,
              type="primary" if key == current else "secondary")


def render_menu(user=None, roles=None):
    """Draw the navigation panel wherever it can actually be seen."""
    if menu_in_main():
        with st.container(key="dj_menu"):
            with st.expander("Studio menu — tools, assistant, documents", expanded=False):
                render_sidebar(user, roles, container=st.container())
        return
    render_sidebar(user, roles)


def render_sidebar(user=None, roles=None, container=None):
    with (container if container is not None else st.sidebar):
        logo = logo_data_uri()
        img = f'<img src="{logo}" alt="">' if logo else ""
        st.markdown(
            f'<div class="dj-sb-brand">{img}<div>'
            f'<div class="dj-sb-title">DrJha<span>GPT</span> PRO</div>'
            f'<div class="dj-sb-sub">{config.BRAND_STUDIO_EYEBROW}</div></div></div>'
            '<hr class="dj-sb-rule">',
            unsafe_allow_html=True,
        )

        if config.ENABLE_AUTH and user:
            sess = auth.session()
            role = config.ROLE_LABELS.get(auth.role(), auth.role())
            name = sess.get("name") or user
            st.markdown(
                f'<div class="dj-sb-user"><span class="dj-sb-ava">'
                f'{html.escape(_initials(name))}</span>'
                f'<b>{html.escape(name)}</b>'
                f'<span class="dj-sb-badge">{html.escape(role)}</span></div>',
                unsafe_allow_html=True,
            )

        # --- Navigation -----------------------------------------------------
        available = studio.allowed_tools()
        current = st.session_state.get("tool", "ask")

        st.markdown('<div class="dj-sb-label">Create</div>', unsafe_allow_html=True)
        for group, keys in studio.TOOL_GROUPS:
            shown = [k for k in keys if k in available]
            if not shown:
                continue
            st.markdown(f'<div class="dj-sb-group">{group}</div>',
                        unsafe_allow_html=True)
            for key in shown:
                _nav_button(key, current)

        _shared = [k for k in ("library", "admin") if k in available
                   and not (k == "library" and not store.enabled())]
        if _shared:
            st.markdown('<div class="dj-sb-label">Team</div>', unsafe_allow_html=True)
            for key in _shared:
                _nav_button(key, current)

        # --- Document details ------------------------------------------------
        with st.expander("Document details"):
            st.text_input("Course / programme", key="meta_course",
                          placeholder="VCF 9 Administration")
            st.text_input("Trainer", key="meta_trainer",
                          value=st.session_state.get("meta_trainer")
                          or (auth.session().get("name") or user or ""))
            st.text_input("Product version", key="meta_version",
                          placeholder="vSphere 8.0 U3",
                          help="Also printed on every document you export.")
            st.date_input("Date", key="meta_date", value=_dt.date.today())

        # --- Assistant --------------------------------------------------------
        st.markdown('<div class="dj-sb-label">Assistant</div>', unsafe_allow_html=True)
        opts = studio.allowed_models()
        cur = st.session_state.get("model", config.LLM_MODEL)
        st.session_state["model"] = st.selectbox(
            "Model", opts, index=opts.index(cur) if cur in opts else 0,
            format_func=_model_label, label_visibility="collapsed")

        # --- Recent (collapsible; long titles get elided on a word boundary) ---
        hist = st.session_state.get("dj_history") or []
        if hist:
            with st.expander(f"Recent ({len(hist)})", expanded=False):
                for i, h in enumerate(hist[:10]):
                    if st.button(f"{h['label']} · {_elide(h['title'], 30)}",
                                 key=f"hist{i}", use_container_width=True,
                                 help=h["title"]):
                        st.session_state["tool"] = h["tool"]
                        st.session_state[f"out::{h['tool']}"] = h["md"]
                        st.rerun()
                if st.button("Clear recent", key="hist_clear",
                             use_container_width=True):
                    st.session_state.pop("dj_history", None)
                    st.rerun()

        # --- Ask: the original assistant --------------------------------------
        # Kept together and last, deliberately. These are the controls from the
        # first version of DrJhaGPT and they belong to the chat, not the studio
        # generators - interleaving them made it unclear what applied to what.
        st.markdown('<hr class="dj-sb-sep">', unsafe_allow_html=True)
        st.markdown('<div class="dj-sb-label">Ask · original assistant</div>',
                    unsafe_allow_html=True)
        if "ask" in available:
            _nav_button("ask", current)
        # Always visible: it was previously hidden unless the Ask tool was open,
        # so it looked like the feature had been removed.
        st.segmented_control("Answer from", ["Website + PDF", "Website", "PDF"],
                             key="scope")
        _ingest_uploads(st.file_uploader("Add a PDF", type=["pdf"],
                                         accept_multiple_files=True,
                                         help="Used by the chat, and by any "
                                              "generator with 'Use my uploaded "
                                              "documents' ticked."))
        docs = st.session_state.get("docs", {})
        for name, (chunks, _v) in docs.items():
            st.caption(f"{_elide(name, 26)} — {len(chunks)} chunks")
        if docs and st.button("Clear documents", use_container_width=True):
            st.session_state.pop("docs", None)
            st.rerun()
        if st.session_state.get("messages"):
            st.download_button("Export chat", data=_chat_markdown(),
                               file_name="drjhagpt-chat.md", mime="text/markdown",
                               use_container_width=True)

        # --- Status ----------------------------------------------------------
        kb = rag.has_knowledge()
        st.markdown('<div class="dj-sb-label">Status</div>', unsafe_allow_html=True)
        dot = "#15935a" if kb else "#c99a00"
        lib = "connected" if store.enabled() else "off"
        st.markdown(
            f'<div class="dj-sb-status">'
            f'Retrieval &nbsp; <b>{config.RETRIEVAL_MODE}</b><br>'
            f'Knowledge base &nbsp; <b>{"loaded" if kb else "not built"}</b>'
            f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            f'background:{dot};vertical-align:middle;margin-left:5px"></span><br>'
            f'Shared library &nbsp; <b>{lib}</b><br>'
            f'<a href="{config.WEBSITE_URL}" target="_blank">drpranayjha.com</a>'
            "</div>",
            unsafe_allow_html=True,
        )

        if config.ENABLE_TRACING and auth.is_admin():
            s = observability.summarize()
            fb = feedback.summary()
            st.markdown('<div class="dj-sb-label">Metrics</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="dj-sb-status"><b>{s.get("traces", 0)}</b> traces<br>'
                f'<b>{fb["up"]}</b> up · <b>{fb["down"]}</b> down</div>',
                unsafe_allow_html=True)

        if config.ENABLE_AUTH and user:
            auth.render_logout()
        st.markdown(f'<div class="dj-sb-ver">v{APP_VERSION}</div>',
                    unsafe_allow_html=True)


# ----------------------------------------------------------------------------- chat (the Ask tool)
def render_sources(results):
    if not results:
        return
    seen, cards = set(), []
    for r in results:
        link, title = r.get("url"), r.get("title", "Article")
        if link and link not in seen:
            seen.add(link)
            cards.append(
                f'<a class="dj-source" href="{link}" target="_blank">'
                f'<span class="dj-source-title">{html.escape(str(title))}</span>'
                '<span class="dj-source-host">drpranayjha.com</span></a>'
            )
    if cards:
        st.markdown(
            '<div class="dj-sources"><div class="dj-sources-label">'
            'Related from drpranayjha.com</div>' + "".join(cards) + "</div>",
            unsafe_allow_html=True,
        )


def render_user(text: str):
    st.markdown(
        f'<div class="dj-user-row"><div class="dj-user-bubble">'
        f'{html.escape(text)}</div></div>',
        unsafe_allow_html=True,
    )


def _ingest_uploads(files):
    """Process newly uploaded PDFs into session-scoped, embedded chunks."""
    if not files:
        return
    docs = st.session_state.setdefault("docs", {})
    for f in files:
        if f.name in docs:
            continue
        try:
            with st.spinner(f"Reading {f.name}…"):
                docs[f.name] = documents.process(f, f.name)
        except Exception as exc:
            st.warning(f"Couldn't read {f.name}: {exc}")


def _search_docs(prompt):
    """Top matches across all uploaded documents for this question."""
    docs = st.session_state.get("docs", {})
    if not docs:
        return []
    qv = retrieval._embed(prompt)
    hits = []
    for _name, (chunks, vecs) in docs.items():
        hits += documents.search(qv, chunks, vecs, top_k=3)
    return sorted(hits, key=lambda h: h["score"], reverse=True)[:3]


def _build_context(results, doc_hits):
    parts = []
    if doc_hits:
        parts.append(documents.format_context(doc_hits))
    parts.append(rag.format_context(results))
    return "\n\n".join(p for p in parts if p)


def render_doc_sources(hits):
    if not hits:
        return
    seen, cards = set(), []
    for h in hits:
        key = (h.get("source"), h.get("page"))
        if key in seen:
            continue
        seen.add(key)
        cards.append(
            '<div class="dj-source" style="cursor:default">'
            f'<span class="dj-source-title">{html.escape(str(h.get("source", "")))}</span>'
            f'<span class="dj-source-host">page {h.get("page", "?")} · your upload</span></div>'
        )
    st.markdown(
        '<div class="dj-sources"><div class="dj-sources-label">'
        'From your uploaded document</div>' + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )


def _record_feedback(idx, rating):
    """Log a 👍/👎 on an assistant message (called via button on_click)."""
    msgs = st.session_state.get("messages", [])
    if not (0 <= idx < len(msgs)):
        return
    msgs[idx]["rating"] = rating
    question = ""
    for j in range(idx - 1, -1, -1):
        if msgs[j]["role"] == "user":
            question = msgs[j]["content"]
            break
    feedback.log({
        "rating": rating,
        "user": auth.session().get("username", "anonymous"),
        "model": st.session_state.get("model"),
        "question": guardrails.redact_pii(question),
        "answer_preview": (msgs[idx].get("content") or "")[:300],
        "sources": [s.get("url") for s in msgs[idx].get("sources", [])],
    })


def _render_feedback(msg, idx):
    if msg.get("rating"):
        st.caption("Thanks — feedback recorded.")
        return
    c1, c2, _ = st.columns([1, 1, 10])
    c1.button("👍", key=f"fb_up_{idx}", help="Helpful",
              on_click=_record_feedback, args=(idx, "up"))
    c2.button("👎", key=f"fb_down_{idx}", help="Not helpful",
              on_click=_record_feedback, args=(idx, "down"))


def _chat_markdown():
    lines = ["# DrJhaGPT conversation\n"]
    for m in st.session_state.get("messages", []):
        who = "You" if m["role"] == "user" else "DrJhaGPT"
        lines.append(f"**{who}:** {m['content']}\n")
        for s in (m.get("sources") or []):
            lines.append(f"> source: {s.get('title', '')} — {s.get('url', '')}")
        lines.append("")
    return "\n".join(lines)


def pick_suggestion(question: str):
    st.session_state.pending = question


def render_empty_state():
    st.markdown(
        '<p class="dj-intro">Ask anything technical — grounded in your published '
        'work and any PDF you upload.</p>',
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, q in enumerate(SUGGESTIONS):
        cols[i % 2].button(q, key=f"sug_{i}", use_container_width=True,
                           on_click=pick_suggestion, args=(q,))


def tool_ask(user, roles):
    """The grounded RAG chat — the original DrJhaGPT, now one tool in the studio."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if not st.session_state.messages and not st.session_state.get("pending"):
        render_empty_state()

    for i, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            render_user(msg["content"])
        else:
            with st.chat_message("assistant", avatar=logo_image()):
                st.markdown(msg["content"])
                if msg.get("sources"):
                    render_sources(msg["sources"])
                if msg.get("doc_sources"):
                    render_doc_sources(msg["doc_sources"])
                _render_feedback(msg, i)

    if st.session_state.pop("_scroll", False):
        _scroll_to_bottom()

    typed = st.chat_input("Ask anything about Intelligent Infrastructure…")
    prompt = typed or st.session_state.pop("pending", None)
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    render_user(prompt)

    # Guardrail: block obvious prompt-injection before any retrieval/model call.
    allowed, reason = guardrails.check_input(prompt)
    if not allowed:
        with st.chat_message("assistant", avatar=logo_image()):
            st.warning(reason)
        st.session_state.messages.append({"role": "assistant", "content": reason,
                                          "sources": []})
        return

    with st.chat_message("assistant", avatar=logo_image()):
        if not config.LLM_READY:
            st.error("Configure an LLM first (see the message above).")
            st.session_state.messages.pop()
            return

        # Observability: trace stage latencies + metadata (question is PII-redacted).
        trace = observability.Trace(guardrails.redact_pii(prompt),
                                    user=user or "anonymous")

        scope = st.session_state.get("scope") or "Website + PDF"
        with st.spinner("Searching…"):
            with trace.span("retrieve"):
                results = rag.retrieve(prompt) if scope != "PDF" else []
                doc_hits = _search_docs(prompt) if scope != "Website" else []
                context = _build_context(results, doc_hits)

        history = [{"role": m["role"], "content": m["content"]}
                   for m in st.session_state.messages[:-1]][-6:]

        try:
            with trace.span("generate"):
                answer = st.write_stream(
                    llm.stream_answer(prompt, context, history,
                                      model=st.session_state.get("model")))
        except Exception as exc:
            studio.show_error(exc)
            st.session_state.messages.pop()
            return

        trace.set(mode=config.RETRIEVAL_MODE, model=st.session_state.get("model"),
                  scope=scope, n_sources=len(results), n_doc_hits=len(doc_hits),
                  sources=[r.get("url") for r in results], roles=roles)
        trace.save()

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": results,
         "doc_sources": doc_hits})
    st.session_state["_scroll"] = True
    st.rerun()


# ----------------------------------------------------------------------------- app
def _run_js(js: str):
    """Execute JS in a 0-height frame that can reach the app DOM."""
    code = f"<script>{js}</script>"
    try:
        st.components.v1.html(code, height=0)
    except Exception:
        try:
            st.html(code, unsafe_allow_javascript=True)
        except Exception:
            pass


def _hide_streamlit_badge():
    """Hide the Community Cloud 'Built with Streamlit' bar + Fullscreen link.

    Bounded on purpose. This used to poll every 500ms forever, which keeps the
    renderer permanently busy (screenshots and headless captures never settle)
    for no benefit: every Streamlit rerun re-injects this component anyway, so a
    short burst plus a DOM observer catches the badge whenever it appears.
    """
    _run_js(
        """
        (function(){
          function scrub(d){ if(!d) return; try{
            d.querySelectorAll('a[href*="streamlit.io"],a[href*="streamlit.app"]').forEach(function(a){a.style.display='none';if(a.parentElement){a.parentElement.style.display='none';}});
            Array.prototype.forEach.call(d.querySelectorAll('button,a,span'),function(el){if(el.childElementCount===0){var t=(el.textContent||'').trim();if(t==='Fullscreen'||t==='Built with Streamlit'||t==='Manage app'){var p=el.closest('div');if(p){p.style.display='none';}}}});
          }catch(e){} }
          function doc(){ try{ if(window.parent&&window.parent!==window){ return window.parent.document; } }catch(e){} return document; }
          function kill(){ scrub(doc()); scrub(document); }
          kill();
          var n=0, t=setInterval(function(){ kill(); if(++n>=12){ clearInterval(t); } },500);
          try{
            var target=doc().body;
            if(target && window.MutationObserver){
              var pending=false;
              new MutationObserver(function(){
                if(pending) return; pending=true;
                setTimeout(function(){ pending=false; kill(); },250);
              }).observe(target,{childList:true,subtree:true});
            }
          }catch(e){}
        })();
        """
    )


def _scroll_to_bottom():
    """Scroll the view to the latest message (Streamlit doesn't auto-scroll)."""
    _run_js(
        """
        (function(){
          var SEL=['[data-testid="stMain"]','[data-testid="stMainBlockContainer"]','section.main','[data-testid="stAppViewContainer"]','[data-testid="stAppScrollToBottomContainer"]'];
          function bottom(d){ try{
            var se=d.scrollingElement||d.documentElement; if(se){ se.scrollTop=se.scrollHeight; }
            SEL.forEach(function(sel){ var el=d.querySelector(sel); if(el){ el.scrollTop=el.scrollHeight; } });
          }catch(e){} }
          function go(){ try{ if(window.parent&&window.parent!==window){ bottom(window.parent.document); } }catch(e){} bottom(document); }
          go(); setTimeout(go,120); setTimeout(go,350); setTimeout(go,700);
        })();
        """
    )


def _tool_group_of(key):
    for group, keys in studio.TOOL_GROUPS:
        if key in keys:
            return group
    return {"ask": "Ask", "library": "Team", "admin": "Team"}.get(key, "")


def render_tool_head(key):
    if key == "ask":
        return
    st.markdown(
        f'<div class="dj-tool-head"><span class="dj-tool-name">'
        f'{html.escape(studio.TOOL_LABELS.get(key, key))}</span>'
        f'<span class="dj-tool-group">{html.escape(_tool_group_of(key))}</span></div>',
        unsafe_allow_html=True)


def main():
    _hide_streamlit_badge()

    authed, user, roles = auth.gate()
    if not authed:
        return

    # A DB user whose password was set by an admin must replace it first.
    if auth.force_password_change():
        return

    st.session_state.setdefault("tool", "ask")
    st.session_state.setdefault("scope", "Website + PDF")

    render_menu(user, roles)
    render_header()

    if config.IS_STAGING:
        st.markdown(f'<div class="dj-env">Test environment ({config.APP_ENV}) — '
                    'not the live studio.</div>', unsafe_allow_html=True)

    if not config.LLM_READY:
        st.warning(
            "**Setup needed:** configure an LLM.\n\n"
            "- **Groq (default):** set `GROQ_API_KEY` (free at https://console.groq.com/keys).\n"
            "- **Gemini (free fallback):** set `GEMINI_API_KEY`.\n"
            "- **Self-hosted:** set `LLM_BASE_URL` to your OpenAI-compatible endpoint "
            "(vLLM / Ollama / NIM)."
        )

    tool = st.session_state.get("tool", "ask")
    if tool not in studio.allowed_tools():
        tool = st.session_state["tool"] = "ask"

    render_tool_head(tool)

    if tool == "ask":
        tool_ask(user, roles)
    elif tool == "library":
        admin.tool_library()
    elif tool == "admin":
        admin.tool_admin()
    else:
        handler = tools.REGISTRY.get(tool)
        if handler:
            handler()
        else:
            st.session_state["tool"] = "ask"
            st.rerun()


if __name__ == "__main__":
    main()
