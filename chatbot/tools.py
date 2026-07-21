"""The studio's generator tools - one form per tool.

Each function renders its form, builds a prompt from `chatbot.prompts`, and hands
it to `studio.emit()`, which owns generation, rendering and export. Tools stay
small on purpose: the shared context row, the grounding switch and the export
machinery all live outside them.
"""
import datetime as _dt

import streamlit as st

from . import config, prompts, studio

# =============================================================================
#  Shared form fragments
# =============================================================================
def _blurb(key):
    st.markdown(f'<p class="dj-tool-blurb">{studio.TOOL_BLURBS.get(key, "")}</p>',
                unsafe_allow_html=True)


def _context_row(key, level=True, audience=False, area_default=0):
    """The 'what technology, which version, how deep' row every tool shares."""
    c1, c2 = st.columns([3, 2])
    area = c1.selectbox("Technology area", config.TECH_AREAS, index=area_default,
                        key=f"area::{key}")
    version = c2.text_input("Product / version", placeholder="e.g. vSphere 8.0 U3",
                            key=f"ver::{key}",
                            help="Named explicitly in the prompt so the output isn't "
                                 "written for the wrong release.")
    lvl = aud = ""
    if level or audience:
        c3, c4 = st.columns(2)
        if level:
            lvl = c3.selectbox("Depth", config.AUDIENCE_LEVELS, index=1,
                               key=f"lvl::{key}")
        if audience:
            target = c4 if level else c3
            aud = target.selectbox("Audience", config.AUDIENCE_ROLES, index=2,
                                   key=f"aud::{key}")
    return area, version, lvl, aud


def _grounding(key, default_site=True):
    """Whether to retrieve from the site index and/or the uploaded PDFs."""
    docs = st.session_state.get("docs") or {}
    c1, c2 = st.columns(2)
    use_site = c1.checkbox("Ground in my published work", value=default_site,
                           key=f"gs::{key}",
                           help="Retrieves matching passages from drpranayjha.com so "
                                "the output follows your own positions and terminology.")
    use_docs = False
    if docs:
        use_docs = c2.checkbox(f"Use my {len(docs)} uploaded document(s)", value=True,
                               key=f"gd::{key}",
                               help="Release notes, an admin guide or an exam "
                                    "blueprint you loaded in the sidebar.")
    else:
        c2.caption("Upload a PDF in the sidebar to ground this in a specific document.")
    return use_site, use_docs


def _fetch(query, use_site, use_docs):
    with st.spinner("Searching your material…"):
        return studio.ground(query, use_site, use_docs)


def _slug(*parts):
    text = "-".join(str(p) for p in parts if p)
    keep = "".join(c if (c.isalnum() or c in " -_") else "" for c in text)
    return ("-".join(keep.split())[:60] or "drjhagpt").lower()


def _today():
    return _dt.date.today().strftime("%Y%m%d")


# =============================================================================
#  Plan & teach
# =============================================================================
def tool_course():
    _blurb("course")
    with st.form("f_course"):
        area, version, level, audience = _context_row("course", audience=True)
        c1, c2 = st.columns(2)
        length = c1.selectbox("Total duration", config.COURSE_LENGTHS, index=1)
        mode = c2.selectbox("Delivery", config.DELIVERY_MODES)
        goals = st.text_area(
            "What must learners be able to do afterwards?", height=90,
            placeholder="Deploy and operate a VCF 9 management domain, and "
                        "troubleshoot the common day-2 failures.")
        use_site, use_docs = _grounding("course")
        go = st.form_submit_button("Build the outline", use_container_width=True)

    context, sources = "", []
    if go:
        context, sources = _fetch(f"{area} {version} course training {goals}",
                                  use_site, use_docs)
    studio.emit("course", go,
                prompts.course_outline(area, version, level, audience, length, mode,
                                       goals, context),
                _slug(area, "course", _today()), f"{area} — Course Outline",
                sources=sources, max_tokens=3400)


def tool_session():
    _blurb("session")
    with st.form("f_session"):
        area, version, level, audience = _context_row("session", audience=True)
        topic = st.text_input("Session topic",
                              placeholder="vSAN ESA storage policies and their failure behaviour")
        c1, c2 = st.columns(2)
        duration = c1.selectbox("Session length", config.SESSION_LENGTHS, index=2)
        mode = c2.selectbox("Delivery", config.DELIVERY_MODES)
        use_site, use_docs = _grounding("session")
        go = st.form_submit_button("Plan the session", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("Session topic", topic)):
            return
        context, sources = _fetch(f"{topic} {area} {version}", use_site, use_docs)
    studio.emit("session", go,
                prompts.session_plan(area, version, level, audience, duration, topic,
                                     mode, context),
                _slug(topic or area, "session"), topic or f"{area} — Session Plan",
                sources=sources, max_tokens=3200)


def tool_slides():
    _blurb("slides")
    with st.form("f_slides"):
        area, version, level, audience = _context_row("slides", audience=True)
        topic = st.text_input("Deck topic",
                              placeholder="Why VCF changes the operating model")
        c1, c2 = st.columns(2)
        count = c1.selectbox("Roughly how many slides",
                             ["8", "10", "12", "15", "20", "25", "30"], index=3)
        duration = c2.selectbox("Talk length", config.SESSION_LENGTHS, index=1)
        use_site, use_docs = _grounding("slides")
        go = st.form_submit_button("Draft the deck", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("Deck topic", topic)):
            return
        context, sources = _fetch(f"{topic} {area} {version}", use_site, use_docs)
    studio.emit("slides", go,
                prompts.slide_outline(area, version, level, audience, topic, count,
                                      duration, context),
                _slug(topic or area, "deck"), topic or f"{area} — Slide Outline",
                sources=sources, max_tokens=3600)


def tool_diagram():
    _blurb("diagram")
    st.caption("Diagrams render live below and export with the document. "
               "If one fails to draw, use Regenerate — the model occasionally "
               "writes invalid Mermaid.")
    with st.form("f_diagram"):
        area, version, level, _ = _context_row("diagram")
        kind = st.selectbox("Diagram type", config.DIAGRAM_TYPES)
        subject = st.text_input(
            "What should it show?",
            placeholder="A VCF 9 management domain: vCenter, NSX managers, SDDC "
                        "Manager, vSAN cluster and their dependencies")
        detail = st.text_area("Anything it must include or leave out (optional)",
                              height=70)
        use_site, use_docs = _grounding("diagram")
        go = st.form_submit_button("Draw it", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("What should it show?", subject)):
            return
        context, sources = _fetch(f"{subject} {area} architecture {version}",
                                  use_site, use_docs)
    studio.emit("diagram", go,
                prompts.diagram(area, version, level, kind, subject, detail, context),
                _slug(subject or area, "diagram"), subject or f"{area} — Diagram",
                temperature=0.35, sources=sources)


def tool_explain():
    _blurb("explain")
    with st.form("f_explain"):
        area, version, _, audience = _context_row("explain", level=False, audience=True)
        topic = st.text_input("Concept to explain",
                              placeholder="How vSphere DRS actually decides to move a VM")
        tone = st.selectbox("Style", config.DOC_TONES)
        use_site, use_docs = _grounding("explain")
        go = st.form_submit_button("Explain it", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("Concept to explain", topic)):
            return
        context, sources = _fetch(f"{topic} {area} {version}", use_site, use_docs)
    studio.emit("explain", go,
                prompts.explainer(area, version, topic, tone, audience, context),
                _slug(topic or area, "explainer"), topic or f"{area} — Explainer",
                sources=sources, max_tokens=3200)


# =============================================================================
#  Hands-on
# =============================================================================
def tool_lab():
    _blurb("lab")
    with st.form("f_lab"):
        area, version, level, _ = _context_row("lab")
        topic = st.text_input("Lab topic",
                              placeholder="Configure and validate a vSAN stretched cluster")
        c1, c2 = st.columns(2)
        duration = c1.selectbox("Time budget", config.SESSION_LENGTHS, index=3)
        environment = c2.selectbox("Lab environment", config.LAB_ENVIRONMENTS)
        solution = st.checkbox("Include the instructor solution key", value=True,
                               help="Turn this off to produce the learner's copy.")
        use_site, use_docs = _grounding("lab")
        go = st.form_submit_button("Write the lab", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("Lab topic", topic)):
            return
        context, sources = _fetch(f"{topic} {area} {version} configuration steps",
                                  use_site, use_docs)
    studio.emit("lab", go,
                prompts.lab_guide(area, version, level, topic, duration, environment,
                                  solution, context),
                _slug(topic or area, "lab"), topic or f"{area} — Lab Guide",
                temperature=0.35, sources=sources, max_tokens=3600)


def tool_demo():
    _blurb("demo")
    with st.form("f_demo"):
        area, version, _, _ = _context_row("demo", level=False)
        topic = st.text_input("What are you demoing?",
                              placeholder="Live migration of a workload domain with HCX")
        c1, c2 = st.columns(2)
        duration = c1.selectbox("Time on stage", config.SESSION_LENGTHS, index=0)
        environment = c2.selectbox("Environment", config.LAB_ENVIRONMENTS)
        use_site, use_docs = _grounding("demo")
        go = st.form_submit_button("Build the runbook", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("What are you demoing?", topic)):
            return
        context, sources = _fetch(f"{topic} {area} {version}", use_site, use_docs)
    studio.emit("demo", go,
                prompts.demo_runbook(area, version, topic, duration, environment, context),
                _slug(topic or area, "demo"), topic or f"{area} — Demo Runbook",
                temperature=0.35, sources=sources)


def tool_troubleshoot():
    _blurb("troubleshoot")
    with st.form("f_trouble"):
        area, version, level, _ = _context_row("troubleshoot")
        symptom = st.text_input(
            "Fault or symptom to build the scenario around",
            placeholder="Hosts randomly disconnect from vCenter after a network change")
        difficulty = st.select_slider(
            "Difficulty", ["Straightforward", "Moderate", "Hard", "Brutal"],
            value="Moderate")
        use_site, use_docs = _grounding("troubleshoot")
        go = st.form_submit_button("Build the scenario", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("Fault or symptom", symptom)):
            return
        context, sources = _fetch(f"{symptom} {area} {version} troubleshooting",
                                  use_site, use_docs)
    studio.emit("troubleshoot", go,
                prompts.troubleshooting(area, version, level, symptom, difficulty, context),
                _slug(symptom or area, "scenario"), symptom or f"{area} — Scenario",
                sources=sources, max_tokens=3200)


# =============================================================================
#  Practice & assess
# =============================================================================
def tool_quiz():
    _blurb("quiz")
    with st.form("f_quiz"):
        area, version, level, _ = _context_row("quiz")
        topic = st.text_input("Topic to assess",
                              placeholder="vSphere networking: vDS, LACP and teaming policies")
        c1, c2 = st.columns(2)
        fmt = c1.selectbox("Question style", [f for f, _ in config.QUIZ_FORMATS])
        count_choice = c2.selectbox("How many questions", config.QUIZ_COUNTS, index=1)
        count = count_choice
        if count_choice == "Custom…":
            count = str(st.number_input("Exactly how many", 1, 100, 12, key="quiz_n"))
        certification = st.selectbox("Match a certification's style (optional)",
                                     config.CERTIFICATIONS)
        use_site, use_docs = _grounding("quiz", default_site=False)
        go = st.form_submit_button("Write the quiz", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("Topic to assess", topic)):
            return
        context, sources = _fetch(f"{topic} {area} {version}", use_site, use_docs)
    studio.emit("quiz", go,
                prompts.quiz(area, version, level, topic, fmt, count, certification,
                             context),
                _slug(topic or area, "quiz"), topic or f"{area} — Quiz",
                temperature=0.45, sources=sources, max_tokens=3800)


def tool_flashcards():
    _blurb("flashcards")
    st.caption("The CSV export drops straight into Anki or Quizlet "
               "(Front, Back, Tag).")
    with st.form("f_cards"):
        area, version, level, _ = _context_row("flashcards")
        topic = st.text_input("Topic", placeholder="Kubernetes scheduling and affinity")
        count = st.selectbox("Number of cards", ["10", "15", "20", "30", "40"], index=2)
        use_site, use_docs = _grounding("flashcards", default_site=False)
        go = st.form_submit_button("Make the deck", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("Topic", topic)):
            return
        context, sources = _fetch(f"{topic} {area} {version}", use_site, use_docs)
    studio.emit("flashcards", go,
                prompts.flashcards(area, version, level, topic, count, context),
                _slug(topic or area, "flashcards"), topic or f"{area} — Flashcards",
                temperature=0.4, sources=sources, max_tokens=3200)


def tool_studyplan():
    _blurb("studyplan")
    with st.form("f_study"):
        certification = st.selectbox("Target certification", config.CERTIFICATIONS,
                                     index=1)
        custom = st.text_input("If 'Other', name the exam", key="study_custom")
        c1, c2 = st.columns(2)
        weeks = c1.selectbox("Time available",
                             ["2 weeks", "4 weeks", "6 weeks", "8 weeks", "12 weeks",
                              "16 weeks"], index=3)
        hours = c2.selectbox("Study time per week",
                             ["3 hours", "5 hours", "8 hours", "10 hours", "15 hours"],
                             index=1)
        level = st.selectbox("Where you're starting from", config.AUDIENCE_LEVELS,
                             index=0)
        background = st.text_area(
            "Relevant experience (optional)", height=70,
            placeholder="Four years on vSphere, no NSX exposure, some scripting.")
        use_site, use_docs = _grounding("studyplan", default_site=False)
        go = st.form_submit_button("Build the plan", use_container_width=True)

    exam = custom.strip() if (custom or "").strip() else certification
    context, sources = "", []
    if go:
        context, sources = _fetch(f"{exam} exam preparation", use_site, use_docs)
    studio.emit("studyplan", go,
                prompts.study_plan(exam, weeks, hours, level, background, context),
                _slug(exam, "study-plan"), f"{exam} — Study Plan",
                sources=sources, max_tokens=3600)


# =============================================================================
#  Code & config
# =============================================================================
def tool_script():
    _blurb("script")
    with st.form("f_script"):
        area, version, level, _ = _context_row("script")
        language = st.selectbox("Language / tool", config.SCRIPT_LANGUAGES)
        task = st.text_area(
            "What should the script do?", height=90,
            placeholder="Report every VM with a snapshot older than 7 days across all "
                        "clusters, and export it to CSV.")
        requirements = st.text_input("Constraints (optional)",
                                     placeholder="Must run unattended from a scheduled task")
        use_site, use_docs = _grounding("script", default_site=False)
        go = st.form_submit_button("Write the script", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("What should the script do?", task)):
            return
        context, sources = _fetch(f"{task} {language} {area}", use_site, use_docs)
    studio.emit("script", go,
                prompts.script(area, language, task, level, version, requirements, context),
                _slug(language, task[:30] if task else area), f"{language} — Script",
                temperature=0.25, sources=sources, max_tokens=3600)


def tool_codeexplain():
    _blurb("codeexplain")
    with st.form("f_codex"):
        c1, c2 = st.columns(2)
        language = c1.selectbox("Language / format", config.SCRIPT_LANGUAGES)
        level = c2.selectbox("Explain for", config.AUDIENCE_LEVELS, index=1)
        code = st.text_area("Paste the code, config or manifest", height=240,
                            placeholder="Paste up to a few hundred lines.")
        focus = st.text_input("Anything specific to focus on? (optional)",
                              placeholder="Why the retry loop is written this way")
        go = st.form_submit_button("Explain it", use_container_width=True)

    if go and not studio.require(("Paste the code", code)):
        return
    studio.emit("codeexplain", go,
                prompts.code_explain(language, code, level, focus),
                _slug(language, "explained"), f"{language} — Code Walkthrough",
                temperature=0.25, max_tokens=3600)


def tool_cheatsheet():
    _blurb("cheatsheet")
    with st.form("f_cheat"):
        area, version, _, audience = _context_row("cheatsheet", level=False,
                                                  audience=True)
        topic = st.text_input("Cheat sheet topic",
                              placeholder="ESXi host troubleshooting from the CLI")
        tone = st.selectbox("Style", config.DOC_TONES)
        use_site, use_docs = _grounding("cheatsheet", default_site=False)
        go = st.form_submit_button("Build the sheet", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("Cheat sheet topic", topic)):
            return
        context, sources = _fetch(f"{topic} {area} {version} commands",
                                  use_site, use_docs)
    studio.emit("cheatsheet", go,
                prompts.cheat_sheet(area, version, topic, audience, tone, context),
                _slug(topic or area, "cheatsheet"), topic or f"{area} — Cheat Sheet",
                temperature=0.25, sources=sources)


# =============================================================================
#  Deliver & publish
# =============================================================================
def tool_handout():
    _blurb("handout")
    with st.form("f_handout"):
        area, version, level, _ = _context_row("handout")
        topic = st.text_input("Session topic")
        covered = st.text_area("What did you cover? (optional but worth filling)",
                               height=90,
                               placeholder="Storage policies, fault domains, the "
                                           "resync behaviour we demoed.")
        use_site, use_docs = _grounding("handout")
        go = st.form_submit_button("Write the handout", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("Session topic", topic)):
            return
        context, sources = _fetch(f"{topic} {covered} {area}", use_site, use_docs)
    studio.emit("handout", go,
                prompts.handout(area, version, level, topic, covered, context),
                _slug(topic or area, "handout"), topic or f"{area} — Handout",
                sources=sources, max_tokens=3400)


def tool_runbook():
    _blurb("runbook")
    with st.form("f_runbook"):
        area, version, _, audience = _context_row("runbook", level=False, audience=True)
        procedure = st.text_input(
            "Procedure",
            placeholder="Patch an ESXi cluster with vSphere Lifecycle Manager")
        environment = st.text_input("Environment", value="Production")
        use_site, use_docs = _grounding("runbook")
        go = st.form_submit_button("Write the runbook", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("Procedure", procedure)):
            return
        context, sources = _fetch(f"{procedure} {area} {version} procedure",
                                  use_site, use_docs)
    studio.emit("runbook", go,
                prompts.runbook(area, version, procedure, environment, audience, context),
                _slug(procedure or area, "runbook"), procedure or f"{area} — Runbook",
                temperature=0.3, sources=sources, max_tokens=3600)


def tool_article():
    _blurb("article")
    with st.form("f_article"):
        area, version, _, _ = _context_row("article", level=False)
        topic = st.text_input("Subject")
        angle = st.text_area("Your angle or argument (optional)", height=70,
                             placeholder="Most VCF sizing exercises start from the "
                                         "wrong number.")
        c1, c2 = st.columns(2)
        length = c1.selectbox("Length",
                              ["600 words", "900 words", "1200 words", "1800 words"],
                              index=1)
        tone = c2.selectbox("Tone", config.DOC_TONES)
        use_site, use_docs = _grounding("article")
        go = st.form_submit_button("Draft the article", use_container_width=True)

    context, sources = "", []
    if go:
        if not studio.require(("Subject", topic)):
            return
        context, sources = _fetch(f"{topic} {angle} {area}", use_site, use_docs)
    studio.emit("article", go,
                prompts.article(area, version, topic, angle, length, tone, context),
                _slug(topic or area, "article"), topic or f"{area} — Article",
                temperature=0.6, sources=sources, max_tokens=3600)


COMMS_KINDS = ["Joining instructions (before the session)",
               "Reminder (the day before)", "Follow-up (after the session)",
               "Course announcement", "Prerequisite / setup instructions",
               "Schedule change or cancellation", "Certificate & feedback request",
               "LinkedIn post"]


def tool_comms():
    _blurb("comms")
    with st.form("f_comms"):
        kind = st.selectbox("Message type", COMMS_KINDS)
        topic = st.text_input("Subject / course",
                             placeholder="VCF 9 Administration — 3-day workshop")
        c1, c2 = st.columns(2)
        audience = c1.selectbox("Audience", config.AUDIENCE_ROLES, index=8)
        tone = c2.selectbox("Tone", config.DOC_TONES)
        details = st.text_area("Details to include", height=100,
                               placeholder="Dates, timings, prerequisites, what to "
                                           "install beforehand, joining link.")
        go = st.form_submit_button("Write it", use_container_width=True)

    if go and not studio.require(("Subject / course", topic)):
        return
    studio.emit("comms", go,
                prompts.comms(kind, topic, audience, details, tone),
                _slug(topic or "comms", "message"), topic or "Trainer Comms",
                temperature=0.55, max_tokens=2200)


# --- Router ------------------------------------------------------------------
REGISTRY = {
    "course": tool_course, "session": tool_session, "slides": tool_slides,
    "diagram": tool_diagram, "explain": tool_explain,
    "lab": tool_lab, "demo": tool_demo, "troubleshoot": tool_troubleshoot,
    "quiz": tool_quiz, "flashcards": tool_flashcards, "studyplan": tool_studyplan,
    "script": tool_script, "codeexplain": tool_codeexplain,
    "cheatsheet": tool_cheatsheet,
    "handout": tool_handout, "runbook": tool_runbook, "article": tool_article,
    "comms": tool_comms,
}
