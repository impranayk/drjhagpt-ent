from chatbot import config, feedback


def test_feedback_log_and_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FEEDBACK_PATH", tmp_path / "fb.jsonl")
    feedback.log({"rating": "up"})
    feedback.log({"rating": "down"})
    feedback.log({"rating": "up"})
    s = feedback.summary()
    assert s["up"] == 2
    assert s["down"] == 1
    assert s["total"] == 3
