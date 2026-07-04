"""Lightweight, zero-infrastructure observability.

Records one structured span-set per request (stage latencies in ms, retrieved
sources, token usage, user, mode) to logs/traces.jsonl. This is the same
trace/span shape Arize Phoenix or an OpenTelemetry backend consume, so it can be
exported to Phoenix later with no code changes to the call sites — but it needs
no server to run today.

Use:
    tr = Trace(question, user="demo")
    with tr.span("retrieve"):
        results = rag.retrieve(q)
    tr.set(mode=config.RETRIEVAL_MODE, sources=[r["url"] for r in results])
    ...
    tr.save()
"""
import json
import time
from contextlib import contextmanager

from . import config


class Trace:
    def __init__(self, question: str, user: str = "anonymous"):
        self.record = {
            "ts": time.time(),
            "user": user,
            "question": question,
            "spans_ms": {},
            "meta": {},
        }

    @contextmanager
    def span(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.record["spans_ms"][name] = round((time.perf_counter() - t0) * 1000, 1)

    def set(self, **kwargs):
        self.record["meta"].update(kwargs)

    def save(self):
        if not config.ENABLE_TRACING:
            return
        try:
            config.TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(config.TRACE_PATH, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(self.record, ensure_ascii=False) + "\n")
        except Exception:
            pass  # never let tracing break the request


def summarize(limit: int = 200) -> dict:
    """Aggregate recent traces (count, avg stage latency, avg sources)."""
    if not config.TRACE_PATH.exists():
        return {"traces": 0}
    rows = []
    with open(config.TRACE_PATH, "r", encoding="utf-8") as fh:
        for line in fh.readlines()[-limit:]:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    if not rows:
        return {"traces": 0}
    stages = {}
    for r in rows:
        for name, ms in r.get("spans_ms", {}).items():
            stages.setdefault(name, []).append(ms)
    avg = {k: round(sum(v) / len(v), 1) for k, v in stages.items()}
    return {"traces": len(rows), "avg_latency_ms": avg}
