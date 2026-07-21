"""The studio engine: the tool registry, the generate/refine loop, and export.

Every generator tool renders a form, then calls `emit()` with the prompt it built.
`emit()` owns everything that happens after: streaming the model, rendering the
branded document, the quick-refine row, the export row (Word / Print / Markdown /
Copy / Copy code / CSV), session history, and publishing to the shared library.

Keeping that here means a new tool is a form plus one `emit()` call.
"""
import csv
import datetime as _dt
import html as _html
import io
import json
import re
from urllib.parse import quote as _urlquote

import streamlit as st
import streamlit.components.v1 as components

from . import auth, config, llm, render, store

# --- Tool registry -----------------------------------------------------------
# (key, label, one-line blurb). Groups below control the sidebar order.
TOOLS = [
    # Plan & teach
    ("course", "Course Outline", "A full multi-day course: modules, outcomes, labs."),
    ("session", "Session Plan", "One session, minute by minute, with a talking track."),
    ("slides", "Slide Outline", "Slide-by-slide with speaker notes, ready for PowerPoint."),
    ("diagram", "Architecture Diagram", "A rendered diagram plus the walkthrough narrative."),
    ("explain", "Concept Explainer", "One concept at L100 to L400, with the analogy."),
    # Hands-on
    ("lab", "Lab Guide", "Tasks, checkpoints, cleanup and an instructor key."),
    ("demo", "Demo Runbook", "A live-demo script with pre-flight and a plan B."),
    ("troubleshoot", "Troubleshooting Scenario", "A broken environment to diagnose in class."),
    # Practice & assess
    ("quiz", "Quiz Builder", "Cert-style questions with an explained answer key."),
    ("flashcards", "Flashcards", "Revision cards, exportable to Anki."),
    ("studyplan", "Certification Study Plan", "A week-by-week plan to an exam date."),
    # Code & config
    ("script", "Script Studio", "PowerCLI, Ansible, Terraform, Python - explained."),
    ("codeexplain", "Code Explainer", "Paste code or config; get a teaching walkthrough."),
    ("cheatsheet", "Cheat Sheet", "A dense one-page command reference to hand out."),
    # Deliver & publish
    ("handout", "Student Handout", "Take-away notes that stand alone after the session."),
    ("runbook", "Runbook / SOP", "An operational procedure with rollback and validation."),
    ("article", "Article Draft", "A drpranayjha.com post drawn from your material."),
    ("comms", "Trainer Comms", "Joining instructions, follow-ups, LinkedIn posts."),
    # Ask + navigation (rendered outside the Create list)
    ("ask", "Ask (Technical)", "Grounded chat over your published work and PDFs."),
    ("library", "Shared Library", "Material the team has published to your track."),
    ("admin", "Admin Console", "Manage people, tracks and access rights."),
]

TOOL_GROUPS = [
    ("Plan & teach", ["course", "session", "slides", "diagram", "explain"]),
    ("Hands-on", ["lab", "demo", "troubleshoot"]),
    ("Practice & assess", ["quiz", "flashcards", "studyplan"]),
    ("Code & config", ["script", "codeexplain", "cheatsheet"]),
    ("Deliver & publish", ["handout", "runbook", "article", "comms"]),
]

TOOL_LABELS = {k: label for k, label, _ in TOOLS}
TOOL_BLURBS = {k: blurb for k, _, blurb in TOOLS}

# Tools whose output is mostly code or a diagram - these get "Copy code".
CODE_TOOLS = {"script", "codeexplain", "cheatsheet", "lab", "demo", "runbook", "diagram"}
# Tools whose output leads with a table that is worth exporting as CSV.
CSV_TOOLS = {"flashcards"}


def allowed_tools() -> list:
    """Tool keys the signed-in user may open, honouring role and per-user rules."""
    keys = [k for k, _, _ in TOOLS]
    sess = auth.session()
    explicit = sess.get("allowed_tools")
    if explicit:                     # a per-user override wins over role defaults
        allowed = set(explicit) | {"ask"}
        return [k for k in keys if k in allowed]

    roles = set(auth.roles())
    if config.ROLE_ADMIN in roles:
        return keys
    out = [k for k in keys if k != "admin"]
    if not auth.is_lead():
        out = [k for k in out if k not in config.LEAD_ONLY_TOOLS]
    if config.ROLE_ASSOCIATE in roles:
        out = [k for k in out if k not in config.ASSOCIATE_BLOCKED_TOOLS]
    return out


def allowed_models() -> list:
    """Models this user may pick."""
    sess = auth.session()
    explicit = sess.get("allowed_models")
    if explicit:
        return [m for m in config.AVAILABLE_MODELS if m in explicit] or list(explicit)
    if auth.is_lead():
        return list(config.AVAILABLE_MODELS)
    return [m for m in config.AVAILABLE_MODELS if m in config.TRAINER_MODELS] \
        or list(config.AVAILABLE_MODELS)[:2]


# --- Grounding ---------------------------------------------------------------
def ground(query: str, use_site: bool = True, use_docs: bool = True):
    """Retrieve supporting passages for a generator prompt.

    Returns (context, sources). Both retrieval paths are best-effort: a studio
    document must still generate if the index is missing or a PDF failed to parse.
    """
    context_parts, sources = [], []
    if use_docs and st.session_state.get("docs"):
        try:
            from . import documents, retrieval

            qv = retrieval._embed(query)
            hits = []
            for _name, (chunks, vecs) in st.session_state["docs"].items():
                hits += documents.search(qv, chunks, vecs, top_k=3)
            hits = sorted(hits, key=lambda h: h["score"], reverse=True)[:4]
            if hits:
                context_parts.append(documents.format_context(hits))
                sources += [{"title": h.get("source", "upload"),
                             "detail": f"page {h.get('page', '?')}"} for h in hits]
        except Exception:
            pass
    if use_site:
        try:
            from . import rag

            results = rag.retrieve(query)
            if results:
                context_parts.append(rag.format_context(results))
                sources += [{"title": r.get("title", "Article"), "url": r.get("url")}
                            for r in results]
        except Exception:
            pass
    return "\n\n".join(p for p in context_parts if p), sources


def render_sources(sources):
    if not sources:
        return
    seen, cards = set(), []
    for s in sources:
        key = s.get("url") or s.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        title = _html.escape(str(s.get("title", "Source")))
        if s.get("url"):
            cards.append(f'<a class="dj-source" href="{_html.escape(s["url"])}" '
                         f'target="_blank"><span class="dj-source-title">{title}</span>'
                         f'<span class="dj-source-host">drpranayjha.com</span></a>')
        else:
            cards.append('<div class="dj-source" style="cursor:default">'
                         f'<span class="dj-source-title">{title}</span>'
                         f'<span class="dj-source-host">'
                         f'{_html.escape(str(s.get("detail", "your upload")))}</span></div>')
    if cards:
        st.markdown('<div class="dj-sources"><div class="dj-sources-label">'
                    'Grounded in</div>' + "".join(cards) + "</div>",
                    unsafe_allow_html=True)


# --- Small UI helpers --------------------------------------------------------
_BTN_CSS = (
    "body{margin:0;}"
    ".djb{width:100%;box-sizing:border-box;height:38px;padding:0 10px;"
    "border:1px solid #d9d9d9;border-radius:3px;background:#fff;color:#141618;"
    "font-family:'Inter',-apple-system,'Segoe UI',Arial,sans-serif;font-size:13.5px;"
    "font-weight:500;cursor:pointer;transition:border-color .15s,color .15s;}"
    ".djb:hover{border-color:#ce242c;color:#ce242c;}"
)


def _payload(text: str) -> str:
    """A JS string literal that can't break out of the <script> block.

    json.dumps does NOT escape '</script>', and the HTML parser closes the script
    on that literal regardless of JS string context.
    """
    return json.dumps(text or "").replace("</", "<\\/")


def copy_button(text: str, label: str = "Copy Markdown", key: str = "c"):
    return ("<style>" + _BTN_CSS + "</style>"
            f'<button class="djb" onclick="dj{key}()">{_html.escape(label)}</button>'
            f"<script>function dj{key}(){{navigator.clipboard.writeText({_payload(text)})"
            ".then(function(){var b=document.querySelector('.djb');var t=b.innerText;"
            "b.innerText='Copied \\u2713';setTimeout(function(){b.innerText=t;},1400);});}"
            "</script>")


def print_button(doc_html: str, label: str = "Print / PDF"):
    """Print the document. It lives inside THIS component frame (hidden on screen),
    so printing works with no popup and no cross-frame call, which the Streamlit
    sandbox blocks."""
    return (
        "<style>" + render.DOC_CSS + _BTN_CSS +
        "@media screen{#djprint{display:none;}}"
        "@media print{.djb{display:none;}body{background:#fff;}"
        "*{-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}"
        ".dj-doc{border:0 !important;box-shadow:none !important;}"
        "@page{margin:12mm;}}"
        "</style>"
        f'<button class="djb" onclick="window.print()">{_html.escape(label)}</button>'
        f'<div id="djprint">{doc_html}</div>'
    )


def _plain_text(md: str) -> str:
    t = md or ""
    t = re.sub(r"^\s*#{1,6}\s*(.+)$", r"\1", t, flags=re.M)
    t = t.replace("**", "").replace("__", "")
    t = re.sub(r"^\s*[-*]\s+", "- ", t, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def share_row(md: str, title: str):
    """Quick share by email or WhatsApp. For a formatted copy, use Print/Word."""
    body = _plain_text(md)
    if len(body) > 2800:
        body = body[:2800].rstrip() + "\n\n… (full version attached - see Print / PDF)"
    mail = (f"mailto:?subject={_urlquote(title + ' — DrJhaGPT Pro')}"
            f"&body={_urlquote(body)}")
    wa = f"https://wa.me/?text={_urlquote(title + chr(10) + chr(10) + body[:1400])}"
    st.markdown(
        f'<div class="dj-share"><span class="dj-share-lbl">Send</span>'
        f'<a class="dj-share-a" href="{mail}">Email</a>'
        f'<a class="dj-share-a" href="{wa}" target="_blank" rel="noopener">WhatsApp</a>'
        "</div>", unsafe_allow_html=True)


def table_to_csv(md: str) -> str:
    """The first Markdown table in the document, as CSV (for Anki / Excel)."""
    rows = []
    for line in (md or "").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if rows:                       # the table ended
                break
            continue
        if re.fullmatch(r"\|[\s:|-]+\|", line):     # the --- separator row
            continue
        cells = [c.strip().replace("**", "") for c in line.strip("|").split("|")]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def doc_meta() -> dict:
    """The Course / Trainer / Version / Date cover row, from the sidebar."""
    meta = {
        "course": (st.session_state.get("meta_course") or "").strip(),
        "trainer": (st.session_state.get("meta_trainer") or "").strip(),
        "version": (st.session_state.get("meta_version") or "").strip(),
    }
    d = st.session_state.get("meta_date")
    if d:
        meta["date"] = d.strftime("%d %b %Y") if hasattr(d, "strftime") else str(d)
    return {k: v for k, v in meta.items() if v}


def is_rate_limit(exc) -> bool:
    s = str(exc).lower()
    return ("rate_limit" in s or "429" in s or "quota" in s or "tokens per day" in s
            or getattr(exc, "status_code", None) == 429)


def show_error(exc):
    """A readable failure card, with the daily-quota case called out."""
    if is_rate_limit(exc):
        cta = ""
        if config.SUPPORT_WHATSAPP:
            cta = (f' <a href="https://wa.me/{config.SUPPORT_WHATSAPP}" target="_blank">'
                   "Message for help</a>.")
        st.markdown(
            '<div class="dj-limit"><b>The free daily model quota is used up.</b><br>'
            "It resets every 24 hours. Switch to a different Assistant in the sidebar "
            "to keep working, or add a second key in Settings." + cta + "</div>",
            unsafe_allow_html=True)
        return
    st.error(f"The model call failed: {exc}")


# --- History -----------------------------------------------------------------
def add_history(tool_key: str, title: str, md: str):
    hist = st.session_state.setdefault("dj_history", [])
    hist.insert(0, {"tool": tool_key, "label": TOOL_LABELS.get(tool_key, tool_key),
                    "title": title, "md": md,
                    "at": _dt.datetime.now().strftime("%H:%M")})
    del hist[24:]


# --- Publish to the shared library ------------------------------------------
def _publish_ui(tool_key: str, md: str, title: str):
    codes = auth.publish_targets()
    labels = store.track_label_map()
    with st.expander("Publish to the shared library"):
        with st.form(f"pub::{tool_key}", clear_on_submit=False):
            c1, c2 = st.columns(2)
            course = c1.text_input("Course / programme",
                                   value=st.session_state.get("meta_course", ""),
                                   key=f"pubc::{tool_key}")
            cohort = c2.text_input("Batch / cohort (optional)", key=f"pubb::{tool_key}")
            picked = st.multiselect(
                "Share with", codes, default=[codes[0]] if codes else [],
                format_func=lambda c: "All tracks" if c == "all" else labels.get(c, c),
                key=f"pubt::{tool_key}")
            tags = st.text_input("Tags (comma-separated, optional)",
                                 key=f"pubg::{tool_key}")
            attach = st.file_uploader("Attach a file (optional)",
                                      key=f"puba::{tool_key}")
            to_site = False
            if config.WEBSITE_POST_READY and tool_key == "article":
                to_site = st.checkbox(
                    "Also create a DRAFT post on drpranayjha.com", value=False,
                    key=f"pubw::{tool_key}")
            go = st.form_submit_button("Publish", use_container_width=True)
        if not go:
            return
        if not picked:
            st.error("Choose at least one track to share with.")
            return
        url = None
        if attach is not None:
            url = store.upload_file(attach.getvalue(), attach.name)
            if url is None:
                st.warning("The file couldn't be uploaded - publishing without it.")
        try:
            store.publish(
                author=auth.session().get("username", "anon"), tool=tool_key,
                title=title, content_md=md, tracks=picked,
                course=course or None, cohort=cohort or None,
                tech_area=st.session_state.get(f"area::{tool_key}"),
                product_version=st.session_state.get("meta_version") or None,
                tags=tags or None, attachment_url=url)
            store.log_event(auth.session().get("username", "anon"), "publish",
                            detail=tool_key, track=auth.track())
            st.success("Published to the shared library.")
        except Exception as exc:
            st.error(f"Couldn't publish: {exc}")
            return
        if to_site:
            try:
                html_doc = render.download_html(md, title, meta=doc_meta())
                where = store.post_to_website(title=title, html=html_doc,
                                              category="post", status="draft")
                st.success(f"Draft created on drpranayjha.com ({where}).")
            except Exception as exc:
                st.warning(f"Published here, but the website post failed: {exc}")


# --- The main loop -----------------------------------------------------------
REFINEMENTS = [
    ("Shorter", "Tighten it. Cut repetition and filler, keep every technical fact, "
                "and keep the same sections."),
    ("Go deeper", "Expand the technical depth: add the mechanism underneath, the "
                  "defaults and limits that matter, and one more worked example. "
                  "Do not pad the prose."),
    ("More commands", "Add concrete, runnable commands and configuration to every "
                      "section where one applies, in fenced code blocks with the "
                      "correct language tag."),
    ("Add a table", "Reformat the parts that suit it (comparisons, schedules, "
                    "ports, sizing, steps) into clear Markdown tables."),
]


def emit(tool_key: str, submitted: bool, prompt: str, filename_base: str,
         title: str, temperature: float = None, sources=None, max_tokens: int = None):
    """Generate / regenerate / refine a document, then render and export it."""
    out_key, prompt_key = f"out::{tool_key}", f"prompt::{tool_key}"
    model = st.session_state.get("model")

    action = None
    if submitted:
        st.session_state[prompt_key] = prompt
        st.session_state[f"src::{tool_key}"] = sources or []
        action = ("gen", prompt)
    elif st.session_state.pop(f"regen::{tool_key}", False) and st.session_state.get(prompt_key):
        action = ("gen", st.session_state[prompt_key])
    elif st.session_state.get(f"refine::{tool_key}"):
        action = ("refine", st.session_state.pop(f"refine::{tool_key}"))

    if action:
        kind, arg = action
        with st.spinner("Writing…" if kind == "gen" else "Revising…"):
            try:
                if kind == "gen":
                    md = "".join(llm.generate(arg, model, temperature=temperature,
                                              max_tokens=max_tokens))
                else:
                    md = "".join(llm.refine(st.session_state.get(out_key, ""), arg, model))
            except Exception as exc:
                show_error(exc)
                return
        st.session_state[out_key] = md
        add_history(tool_key, title, md)
        store.log_event(auth.session().get("username", "anon"),
                        "generate" if kind == "gen" else "refine",
                        detail=tool_key, track=auth.track())

    md = st.session_state.get(out_key)
    if not md:
        return

    logo = _logo_uri()
    meta = doc_meta()
    # Diagrams need their own component frame (Streamlit's Markdown surface can't
    # run the Mermaid script), so the document is drawn in segments.
    for kind, val in render.doc_segments(md, logo, meta, config.BRAND_FULL):
        if kind == "mermaid":
            components.html(render.mermaid_frame(val), height=470, scrolling=True)
        else:
            st.markdown(val, unsafe_allow_html=True)

    render_sources(st.session_state.get(f"src::{tool_key}"))

    # Quick refine
    st.markdown('<p class="dj-refine-label">Refine</p>', unsafe_allow_html=True)
    cols = st.columns(len(REFINEMENTS) + 1)
    for i, (label, instruction) in enumerate(REFINEMENTS):
        if cols[i].button(label, key=f"rf{i}::{tool_key}", use_container_width=True):
            st.session_state[f"refine::{tool_key}"] = instruction
            st.rerun()
    if cols[-1].button("Regenerate", key=f"rg::{tool_key}", use_container_width=True):
        st.session_state[f"regen::{tool_key}"] = True
        st.rerun()

    # Export
    doc_html = render.to_document(md, logo, meta, config.BRAND_FULL)
    word_html = render.download_html(md, title, logo, meta, eyebrow=config.BRAND_FULL)
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.download_button("Word", word_html, file_name=f"{filename_base}.doc",
                           mime="application/msword", key=f"dlw::{tool_key}",
                           use_container_width=True)
    with e2:
        components.html(print_button(doc_html), height=44)
    with e3:
        st.download_button("Markdown", md, file_name=f"{filename_base}.md",
                           mime="text/markdown", key=f"dlm::{tool_key}",
                           use_container_width=True)
    with e4:
        components.html(copy_button(md, key=tool_key.replace("-", "")), height=44)

    extras = []
    if tool_key in CODE_TOOLS:
        blocks = render.code_blocks(md)
        if blocks:
            extras.append(("code", "\n\n".join(b for _, b in blocks)))
    if tool_key in CSV_TOOLS:
        csv_text = table_to_csv(md)
        if csv_text:
            extras.append(("csv", csv_text))
    if tool_key == "diagram":
        for src in render.mermaid_blocks(md):
            extras.append(("mermaid", render.clean_mermaid(src)))
            break
    if extras:
        xc = st.columns(max(len(extras), 3))
        for i, (kind, payload) in enumerate(extras):
            with xc[i]:
                if kind == "code":
                    components.html(copy_button(payload, "Copy code",
                                                key="cd" + tool_key), height=44)
                elif kind == "mermaid":
                    components.html(copy_button(payload, "Copy Mermaid",
                                                key="mm" + tool_key), height=44)
                else:
                    st.download_button("CSV (Anki / Excel)", payload,
                                       file_name=f"{filename_base}.csv",
                                       mime="text/csv", key=f"dlc::{tool_key}",
                                       use_container_width=True)

    share_row(md, title)
    st.caption("Draft — review before you teach from it. Anything the model was "
               "unsure of is marked **[verify]**.")

    if store.enabled() and auth.can_publish():
        _publish_ui(tool_key, md, title)


def _logo_uri() -> str:
    import base64
    from functools import lru_cache

    @lru_cache(maxsize=1)
    def _cached():
        try:
            if config.LOGO_PATH.exists():
                return ("data:image/png;base64,"
                        + base64.b64encode(config.LOGO_PATH.read_bytes()).decode())
        except OSError:
            pass
        return ""

    return _cached()


def require(*named) -> bool:
    """True when every (label, value) pair is filled; otherwise flags the gaps."""
    missing = [label for label, value in named if not (value or "").strip()]
    if missing:
        st.warning("Fill in: " + ", ".join(missing) + ".")
        return False
    return True
