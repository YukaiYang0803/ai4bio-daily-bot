import json
import os
from datetime import datetime, timezone


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

SEEN_PATH = os.path.join(DATA_DIR, "seen_papers.json")


def load_seen():
    if not os.path.exists(SEEN_PATH):
        return {"sent": {}, "candidates": {}}
    with open(SEEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_seen(data):
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_already_sent(arxiv_id):
    seen = load_seen()
    return arxiv_id in seen.get("sent", {})


def mark_sent(arxiv_ids):
    seen = load_seen()
    today = datetime.now(timezone.utc).isoformat()
    for aid in arxiv_ids:
        seen.setdefault("sent", {})[aid] = today
    save_seen(seen)


def mark_candidates(arxiv_ids):
    seen = load_seen()
    today = datetime.now(timezone.utc).isoformat()
    for aid in arxiv_ids:
        seen.setdefault("candidates", {})[aid] = today
    save_seen(seen)


def save_daily_log(date_str, log_data):
    path = os.path.join(LOGS_DIR, f"{date_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2, default=str)
