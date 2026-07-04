from chatbot import config, observability


def test_trace_records_and_summarizes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TRACE_PATH", tmp_path / "traces.jsonl")
    monkeypatch.setattr(config, "ENABLE_TRACING", True)

    tr = observability.Trace("a question", user="tester")
    with tr.span("retrieve"):
        pass
    with tr.span("generate"):
        pass
    tr.set(mode="hybrid", n_sources=3)
    tr.save()

    summary = observability.summarize()
    assert summary["traces"] >= 1
    assert "retrieve" in summary["avg_latency_ms"]
    assert "generate" in summary["avg_latency_ms"]


def test_tracing_disabled_writes_nothing(tmp_path, monkeypatch):
    path = tmp_path / "none.jsonl"
    monkeypatch.setattr(config, "TRACE_PATH", path)
    monkeypatch.setattr(config, "ENABLE_TRACING", False)
    observability.Trace("q").save()
    assert not path.exists()
