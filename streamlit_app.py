"""DrJhaGPT — an open-source RAG chatbot with a brand-matched editorial UI.

Stack: Groq (open LLMs) for generation + retrieval over drpranayjha.com content.
Visual design mirrors drpranayjha.com: white editorial theme, Inter/Oswald type,
charcoal ink (#141618) with a red accent (#ce242c).
"""
import base64
import html
from functools import lru_cache

import streamlit as st

from chatbot import (auth, config, documents, feedback, guardrails, llm,
                     observability, rag, retrieval)

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
    page_title=config.BRAND_NAME,
    page_icon=logo_image(),
    layout="centered",
    initial_sidebar_state="expanded",   # show Options (model picker + PDF upload) by default
)

# ----------------------------------------------------------------------------- styling
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Oswald:wght@500;600;700&display=swap');

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
[class*="_profileContainer"], [class*="profileContainer"],
a[href*="streamlit.io"], a[href*="streamlit.app"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent; height: 0; }
/* Breathing room above the New chat button (esp. in the narrow widget) */
.st-key-new_chat { margin-top: 6px; }

.block-container { max-width: 800px; padding-top: 1.6rem; padding-bottom: 6rem; }

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
.dj-journal { font-family: 'Inter', sans-serif; font-style: italic; color: var(--accent);
              font-size: clamp(10px, 3vw, 11px); font-weight: 500; letter-spacing: .2px;
              line-height: 1.2; margin: 4px 0 0 !important; padding: 0 !important;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dj-rule { height: 1.5px; background: var(--accent); width: 100%; border: 0; margin: 14px 0 6px;
           border-radius: 0; }

/* ---- Chat messages ---- */
[data-testid="stChatMessage"] { background: transparent; padding: .35rem 0; }
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li { font-size: 15.5px; line-height: 1.7; }
[data-testid="stChatMessage"] a { color: var(--accent); text-decoration: none; border-bottom: 1px solid rgba(206,36,44,.35); }
[data-testid="stChatMessage"] a:hover { border-bottom-color: var(--accent); }
[data-testid="stChatMessage"] h1, [data-testid="stChatMessage"] h2, [data-testid="stChatMessage"] h3 {
  font-family: 'Oswald', sans-serif; color: var(--ink); letter-spacing: .2px; margin-top: .4rem; }

/* ---- User question bubble (right-aligned, grey) ---- */
.dj-user-row { display: flex; justify-content: flex-end; margin: 12px 0 4px; }
.dj-user-bubble { background: var(--panel); color: var(--ink); border: 1px solid var(--border);
  border-right: 3px solid var(--accent);
  border-radius: 14px 14px 4px 14px; padding: 9px 14px 9px 16px; max-width: 82%;
  font-size: 15px; line-height: 1.55; white-space: pre-wrap; }

/* ---- "Related reading" source cards ---- */
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

/* ---- Suggestion chips (empty state) ---- */
.dj-intro { color: var(--muted); font-size: 14.5px; margin: 6px 0 14px; }
div[data-testid="stButton"] > button {
  border: 1px solid var(--border); background: #fff; color: var(--ink);
  border-radius: 999px; padding: 8px 16px; font-size: 13.5px; font-weight: 500;
  text-align: left; transition: all .15s; }
div[data-testid="stButton"] > button:hover {
  border-color: var(--accent); color: var(--accent); background: #fff; }

/* "New chat" button — red outline that fills on hover */
.st-key-new_chat button { border: 1.5px solid var(--accent) !important;
  color: var(--accent) !important; text-align: center !important; }
.st-key-new_chat button:hover { background: var(--accent) !important; color: #fff !important; }

/* ---- Chat input ---- */
[data-testid="stChatInput"] { border: 1.5px solid var(--accent) !important;
  border-radius: 12px !important; background: #fff !important; }
[data-testid="stChatInput"] > div { border: 0 !important; background: transparent !important; }
[data-testid="stChatInput"]:focus-within { box-shadow: 0 0 0 3px rgba(206,36,44,.15) !important; }
/* Red send button */
[data-testid="stChatInputSubmitButton"] { background: var(--accent) !important;
  border-radius: 8px !important; }
[data-testid="stChatInputSubmitButton"]:hover { background: var(--accent-dark) !important; }
[data-testid="stChatInputSubmitButton"] svg { color: #fff !important; fill: #fff !important; }

/* ---- Branded sidebar ---- */
[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid var(--border); }
.dj-sb-brand { display: flex; align-items: center; gap: 10px; }
.dj-sb-brand img { width: 36px; height: 36px; border-radius: 8px; border: 2px solid var(--accent); }
.dj-sb-title { font-family: 'Oswald', sans-serif; font-weight: 700; font-size: 21px; color: var(--ink); line-height: 1; }
.dj-sb-title span { color: var(--accent); }
.dj-sb-sub { font-family: 'Inter', sans-serif; font-style: italic; color: var(--accent); font-size: 10.5px; margin-top: 2px; }
.dj-sb-rule { height: 2px; background: var(--accent); border: 0; margin: 10px 0 12px; width: 100%; }
.dj-sb-label { font-family: 'Oswald', sans-serif; color: var(--accent); font-size: 10.5px; letter-spacing: 2px;
  font-weight: 600; text-transform: uppercase; margin: 16px 0 7px; }
.dj-sb-user { display: flex; align-items: center; gap: 8px; background: var(--panel); border: 1px solid var(--border);
  border-left: 3px solid var(--accent); border-radius: 8px; padding: 8px 11px; margin-bottom: 8px; font-size: 13px; color: var(--ink); }
.dj-sb-user b { font-weight: 700; }
.dj-sb-badge { background: var(--accent); color: #fff; font-size: 9px; font-weight: 600; letter-spacing: .5px;
  text-transform: uppercase; padding: 2px 8px; border-radius: 999px; margin-left: auto; }
.dj-sb-status { font-size: 12px; color: var(--muted); line-height: 1.9; }
.dj-sb-status b { color: var(--ink); font-weight: 600; }
.dj-sb-status a { color: var(--accent); text-decoration: none; }

/* Sidebar buttons: centered + consistent */
[data-testid="stSidebar"] div[data-testid="stButton"] > button,
[data-testid="stSidebar"] div[data-testid="stDownloadButton"] > button {
  text-align: center !important; border-radius: 8px !important; }

/* Model picker + PDF uploader (brand accents) */
[data-testid="stFileUploaderDropzone"] { border: 1.5px dashed var(--accent) !important;
  background: #fff !important; border-radius: 10px !important; }
[data-baseweb="select"] > div:focus-within { border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px rgba(206,36,44,.12) !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------- components
def clear_chat():
    st.session_state.messages = []
    st.session_state.pop("pending", None)


def render_header():
    if "mini" in st.query_params:
        # Compact header for the floating widget (its own bar shows the brand).
        _, right = st.columns([2, 1])
        with right:
            st.button("↺  New chat", key="new_chat", on_click=clear_chat,
                      use_container_width=True)
        return
    logo = logo_data_uri()
    img = f'<img src="{logo}" alt="logo">' if logo else ""
    left, right = st.columns([5, 1.4], vertical_alignment="center")
    with left:
        st.markdown(
            f"""
            <div class="dj-masthead">
              {img}
              <div class="dj-headtext">
                <h1 class="dj-title">DrJha<span class="accent">GPT</span></h1>
                <p class="dj-journal">{config.BRAND_EYEBROW}</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.button("↺  New chat", key="new_chat", on_click=clear_chat,
                  use_container_width=True)
    st.markdown('<hr class="dj-rule">', unsafe_allow_html=True)


def render_sidebar(user=None, roles=None):
    with st.sidebar:
        logo = logo_data_uri()
        img = f'<img src="{logo}" alt="">' if logo else ""
        st.markdown(
            f'<div class="dj-sb-brand">{img}<div>'
            f'<div class="dj-sb-title">DrJha<span>GPT</span></div>'
            f'<div class="dj-sb-sub">{config.BRAND_EYEBROW}</div></div></div>'
            '<hr class="dj-sb-rule">',
            unsafe_allow_html=True,
        )

        if config.ENABLE_AUTH and user:
            role = (roles or ["user"])[0]
            st.markdown(
                f'<div class="dj-sb-user">👤 <b>{user}</b>'
                f'<span class="dj-sb-badge">{role}</span></div>',
                unsafe_allow_html=True,
            )
            auth.render_logout()

        kb = rag.has_knowledge()
        st.markdown('<div class="dj-sb-label">Status</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="dj-sb-status">'
            f'Model &nbsp; <b>{config.LLM_MODEL}</b><br>'
            f'Retrieval &nbsp; <b>{config.RETRIEVAL_MODE}</b><br>'
            f'Knowledge base &nbsp; <b>{"loaded" if kb else "not built"}</b> {"✅" if kb else "⚠️"}<br>'
            f'🌐 <a href="{config.WEBSITE_URL}" target="_blank">drpranayjha.com</a>'
            '</div>',
            unsafe_allow_html=True,
        )

        if config.ENABLE_TRACING and roles and "admin" in roles:
            s = observability.summarize()
            fb = feedback.summary()
            st.markdown('<div class="dj-sb-label">Metrics</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="dj-sb-status">📊 <b>{s.get("traces", 0)}</b> traces<br>'
                f'👍 <b>{fb["up"]}</b> · 👎 <b>{fb["down"]}</b> feedback</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="dj-sb-label">Options</div>', unsafe_allow_html=True)
        _opts = list(dict.fromkeys([config.LLM_MODEL] + config.AVAILABLE_MODELS))
        _cur = st.session_state.get("model", config.LLM_MODEL)
        st.session_state["model"] = st.selectbox(
            "Model", _opts, index=_opts.index(_cur) if _cur in _opts else 0)
        _ingest_uploads(st.file_uploader("Chat with a PDF", type=["pdf"],
                                         accept_multiple_files=True))
        _docs = st.session_state.get("docs", {})
        for _name, (_ch, _v) in _docs.items():
            st.caption(f"📄 {_name} — {len(_ch)} chunks")
        if _docs and st.button("Clear documents", use_container_width=True):
            st.session_state.pop("docs", None)
            st.rerun()

        if st.session_state.get("messages"):
            st.download_button("⬇ Export chat", data=_chat_markdown(),
                               file_name="drjhagpt-chat.md", mime="text/markdown",
                               use_container_width=True)

        if st.button("Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.rerun()


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
                f'<span class="dj-source-title">{title}</span>'
                f'<span class="dj-source-host">drpranayjha.com ↗</span></a>'
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
        "user": (st.session_state.get("dj_auth") or {}).get("username", "anonymous"),
        "model": st.session_state.get("model"),
        "question": guardrails.redact_pii(question),
        "answer_preview": (msgs[idx].get("content") or "")[:300],
        "sources": [s.get("url") for s in msgs[idx].get("sources", [])],
    })


def _render_feedback(msg, idx):
    if msg.get("rating"):
        st.caption("✓ Thanks — feedback recorded.")
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
        '<p class="dj-intro">Ask Pranay anything — or start with one of these:</p>',
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, q in enumerate(SUGGESTIONS):
        cols[i % 2].button(q, key=f"sug_{i}", use_container_width=True,
                           on_click=pick_suggestion, args=(q,))


# ----------------------------------------------------------------------------- app
def _hide_streamlit_badge():
    """Remove the Community Cloud 'Built with Streamlit' bar + Fullscreen link.

    CSS can't reliably target it, so we run JS in a same-origin child frame that
    walks the parent DOM and hides those elements by their link/text (robust to
    Streamlit's changing class names). Re-runs on an interval since the badge is
    injected after load.
    """
    st.html(
        """<script>
        (function(){
          function scrub(d){ if(!d) return; try{
            d.querySelectorAll('a[href*="streamlit.io"],a[href*="streamlit.app"]').forEach(function(a){a.style.display='none';if(a.parentElement){a.parentElement.style.display='none';}});
            Array.prototype.forEach.call(d.querySelectorAll('button,a,span'),function(el){if(el.childElementCount===0){var t=(el.textContent||'').trim();if(t==='Fullscreen'||t==='Built with Streamlit'){var p=el.closest('div');if(p){p.style.display='none';}}}});
          }catch(e){} }
          function kill(){ scrub(document); try{ if(window.parent&&window.parent!==window){ scrub(window.parent.document); } }catch(e){} }
          setInterval(kill,400); kill();
        })();
        </script>""",
        unsafe_allow_javascript=True,
    )


def main():
    _hide_streamlit_badge()

    # Phase 2: open-source login gate (no-op if ENABLE_AUTH is off).
    authed, user, roles = auth.gate()
    if not authed:
        return

    render_sidebar(user, roles)
    render_header()

    if not config.LLM_READY:
        st.warning(
            "**Setup needed:** configure an LLM.\n\n"
            "- **Groq (default):** set `GROQ_API_KEY` (free at https://console.groq.com/keys).\n"
            "- **Self-hosted:** set `LLM_BASE_URL` to your OpenAI-compatible endpoint "
            "(vLLM / Ollama / NIM)."
        )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Empty state: intro + suggestion chips.
    if not st.session_state.messages and not st.session_state.get("pending"):
        render_empty_state()

    # Replay history.
    for msg in st.session_state.messages:
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

    typed = st.chat_input("Ask Pranay anything about Intelligent Infrastructure…")
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
        st.session_state.messages.append({"role": "assistant", "content": reason, "sources": []})
        return

    with st.chat_message("assistant", avatar=logo_image()):
        if not config.LLM_READY:
            st.error("Configure an LLM first (see the message above).")
            st.session_state.messages.pop()
            return

        # Observability: trace stage latencies + metadata (question is PII-redacted).
        trace = observability.Trace(guardrails.redact_pii(prompt), user=user or "anonymous")

        with st.spinner("Searching…"):
            with trace.span("retrieve"):
                results = rag.retrieve(prompt)
                doc_hits = _search_docs(prompt)
                context = _build_context(results, doc_hits)

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
        ][-6:]

        try:
            with trace.span("generate"):
                answer = st.write_stream(
                    llm.stream_answer(prompt, context, history,
                                      model=st.session_state.get("model")))
        except Exception as exc:
            st.error(f"Sorry — the model call failed: {exc}")
            st.session_state.messages.pop()
            return

        trace.set(mode=config.RETRIEVAL_MODE, model=st.session_state.get("model"),
                  n_sources=len(results), n_doc_hits=len(doc_hits),
                  sources=[r.get("url") for r in results], roles=roles)
        trace.save()

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": results, "doc_sources": doc_hits}
    )
    st.rerun()


if __name__ == "__main__":
    main()
