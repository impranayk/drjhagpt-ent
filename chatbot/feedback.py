"""Answer feedback (👍/👎), logged for the improvement / evaluation loop.

Each rating is appended to logs/feedback.jsonl with the question, a preview of the
answer, its sources, model, and user — the raw material for spotting weak spots
and building a better golden eval set over time.
"""
import json
import time

from . import config


def log(record: dict):
    try:
        config.FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(config.FEEDBACK_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), **record}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def summary() -> dict:
    if not config.FEEDBACK_PATH.exists():
        return {"total": 0, "up": 0, "down": 0}
    up = down = 0
    with open(config.FEEDBACK_PATH, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                rating = json.loads(line).get("rating")
            except Exception:
                continue
            if rating == "up":
                up += 1
            elif rating == "down":
                down += 1
    return {"total": up + down, "up": up, "down": down}
