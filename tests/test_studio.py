"""The studio: every tool renders, and the document pipeline behaves."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from chatbot import config, prompts, render, studio, tools

APP = str(Path(__file__).resolve().parent.parent / "streamlit_app.py")


# --- Registry ----------------------------------------------------------------
def test_every_generator_tool_has_a_handler():
    """A tool in the sidebar with no handler would dead-end the router."""
    grouped = {k for _g, keys in studio.TOOL_GROUPS for k in keys}
    assert grouped == set(tools.REGISTRY), (
        f"missing handler: {grouped - set(tools.REGISTRY)}; "
        f"orphan handler: {set(tools.REGISTRY) - grouped}")


def test_every_tool_key_is_registered_with_a_label():
    for key in tools.REGISTRY:
        assert studio.TOOL_LABELS.get(key), f"{key} has no label"
        assert studio.TOOL_BLURBS.get(key), f"{key} has no blurb"


def test_prompt_builders_produce_a_titled_markdown_brief():
    """Each builder must ask for the house format, or documents render badly."""
    built = [
        prompts.course_outline("VMware vSphere", "8.0 U3", "L200", "Sysadmins",
                               "2 days", "ILT", "operate a cluster"),
        prompts.session_plan("Kubernetes", "1.31", "L300", "SRE", "1 hour",
                             "scheduling", "VILT"),
        prompts.diagram("VCF", "9.0", "L300", "Architecture", "management domain", ""),
        prompts.quiz("AWS", "", "L200", "VPC", "Multiple choice", "10",
                     "AWS Solutions Architect Associate"),
        prompts.script("VMware vSphere", "PowerCLI", "list stale snapshots",
                       "L200", "8.0", ""),
        prompts.code_explain("Python", "print('hi')", "L100", ""),
        prompts.runbook("VMware vSphere", "8.0", "patch a cluster", "prod", "Ops"),
    ]
    for text in built:
        assert "'# " in text or "'# '" in text or "# " in text
        assert len(text) > 300


def test_grounding_block_is_omitted_when_there_is_no_context():
    without = prompts.explainer("Kubernetes", "1.31", "scheduling", "", "", "")
    with_ctx = prompts.explainer("Kubernetes", "1.31", "scheduling", "", "",
                                 "Pods bind to nodes via the scheduler.")
    assert "GROUNDING" not in without
    assert "GROUNDING" in with_ctx
    assert "Pods bind to nodes" in with_ctx


# --- Renderer ----------------------------------------------------------------
SAMPLE = """# Sample Document

## Objective
Understand the layout.

## Diagram
```mermaid
flowchart TD
  a[SDDC Manager (deploys)] --> b[vCenter Server];
```

## Commands
```powershell
Get-VMHost | Where-Object { $_.ConnectionState -ne "Connected" }
```

**Checkpoint:** hosts show Connected.

| Component | Role |
|---|---|
| vCenter | management |
"""


def test_document_has_icons_meta_table_and_a_language_chip():
    html = render.to_document(SAMPLE, "", {"course": "VCF 9", "trainer": "Pranay"})
    assert "sec-ico" in html                      # section icons
    assert "dj-meta" in html and "VCF 9" in html  # cover row
    assert "<table>" in html
    assert 'data-lang="powershell"' in html       # language chip survived


def test_mermaid_is_split_out_for_its_own_component_frame():
    kinds = [k for k, _ in render.doc_segments(SAMPLE, "", None)]
    assert kinds == ["html", "mermaid", "html"]


def test_clean_mermaid_repairs_the_mistakes_models_make():
    fixed = render.clean_mermaid(
        "flowchart TD\n  a[SDDC Manager (deploys)] --> b[vCenter];\n  %% a comment\n")
    assert "(" not in fixed and ")" not in fixed   # parens break the parser
    assert ";" not in fixed
    assert "%%" not in fixed


def test_mermaid_source_without_a_declaration_gets_one():
    assert render.clean_mermaid("a[One] --> b[Two]").startswith("flowchart TD")


def test_subgraph_id_with_spaces_is_slugified():
    """Observed live: the model writes 'subgraph Management Domain[...]', which
    is a Mermaid parse error and renders nothing at all."""
    fixed = render.clean_mermaid(
        "flowchart LR\n  subgraph Management Domain[Management Domain]\n"
        "    vc1[vCenter Server]\n  end\n  vc1 -->| manages | esxi1[ESXi Host]\n")
    assert "subgraph ManagementDomain[Management Domain]" in fixed
    assert "-->|manages|" in fixed              # padded pipes normalised
    assert "end" in fixed


def test_code_is_protected_from_the_prose_normaliser():
    """A hyphen inside a command must not be rewritten into a list item."""
    md = "Run this:\n\n```bash\ntar -xzf pkg.tgz -C /tmp\n```\n"
    html = render.to_document(md, "")
    assert "tar -xzf pkg.tgz -C /tmp" in render.code_blocks(md)[0][1]
    assert "<li>xzf" not in html


def test_raw_html_from_the_model_is_stripped():
    html = render.to_document("# T\n\n<script>alert(1)</script>\n\nhi", "")
    assert "<script" not in html
    assert "alert(1)" in html or "hi" in html     # text may survive; the tag must not


def test_download_file_is_self_contained_and_prints():
    out = render.download_html(SAMPLE, "Sample", "", {"course": "VCF 9"})
    assert out.startswith("<!doctype html>")
    assert "@media print" in out
    assert "mermaid.esm" in out                   # diagrams render in the saved file


def test_table_to_csv_extracts_the_flashcard_deck():
    csv_text = studio.table_to_csv(
        "# Deck\n\n| Front | Back | Tag |\n|---|---|---|\n"
        "| What is DRS? | Load balancing | drs |\n| What is HA? | Restart | ha |\n")
    lines = csv_text.strip().splitlines()
    assert lines[0] == "Front,Back,Tag"
    assert len(lines) == 3


# --- Access control ----------------------------------------------------------
def test_lead_only_and_associate_rules_are_disjointly_enforced(monkeypatch):
    """An associate must not reach the syllabus-setting tools."""
    monkeypatch.setattr(config, "ENABLE_AUTH", True)
    import chatbot.auth as auth

    monkeypatch.setattr(auth, "session", lambda: {"roles": [config.ROLE_ASSOCIATE]})
    monkeypatch.setattr(auth, "roles", lambda: [config.ROLE_ASSOCIATE])
    monkeypatch.setattr(auth, "is_lead", lambda: False)
    allowed = studio.allowed_tools()
    assert "admin" not in allowed
    for blocked in config.LEAD_ONLY_TOOLS + config.ASSOCIATE_BLOCKED_TOOLS:
        assert blocked not in allowed
    assert "ask" in allowed and "lab" in allowed


def test_tables_are_prefixed_so_a_project_can_be_shared():
    """Generic names would collide with a sibling app in the same Supabase
    project, and `create table if not exists` fails silently when they do."""
    from chatbot import store

    for logical in ("app_users", "events", "access_requests", "library", "tracks"):
        assert store.table_name(logical) == "dj_" + logical
    # Applying the prefix twice would point at a table that doesn't exist.
    assert store.table_name("dj_library") == "dj_library"


def test_admin_sees_every_tool(monkeypatch):
    import chatbot.auth as auth

    monkeypatch.setattr(auth, "session", lambda: {"roles": [config.ROLE_ADMIN]})
    monkeypatch.setattr(auth, "roles", lambda: [config.ROLE_ADMIN])
    monkeypatch.setattr(auth, "is_lead", lambda: True)
    assert set(studio.allowed_tools()) == {k for k, _, _ in studio.TOOLS}


# --- End-to-end render -------------------------------------------------------
@pytest.mark.parametrize("tool_key", sorted(tools.REGISTRY) + ["ask", "library"])
def test_each_tool_page_renders_without_exception(tool_key, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_AUTH", False)
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["tool"] = tool_key
    at.run()
    assert not at.exception, f"{tool_key} raised: {at.exception}"
