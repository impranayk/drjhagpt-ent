from pathlib import Path

from streamlit.testing.v1 import AppTest

from chatbot import config

APP = str(Path(__file__).resolve().parent.parent / "streamlit_app.py")


def test_app_renders_with_chat_history(monkeypatch):
    """Replaying an existing conversation must not error (regression: the
    feedback loop referenced an undefined index)."""
    monkeypatch.setattr(config, "ENABLE_AUTH", False)
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["messages"] = [
        {"role": "user", "content": "What is VMware HCX?"},
        {"role": "assistant", "content": "HCX is a migration tool.",
         "sources": [], "doc_sources": []},
    ]
    at.run()
    assert not at.exception
