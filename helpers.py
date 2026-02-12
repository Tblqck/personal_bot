import os
import csv
import json
from datetime import datetime, timezone
from difflib import SequenceMatcher

# -----------------------
# CSV & JSON paths
# -----------------------
TASKS_CSV = "tasks.csv"
CONTEXT_CSV = "chat_context.csv"
DATABASE_JSON = "database.json"

CSV_FIELDS = ["user_id", "title", "details", "due", "status", "google_status", "google_id", "ai_comment"]
CONTEXT_FIELDS = ["user_id", "timestamp", "role", "message"]

# -----------------------
# Helpers
# -----------------------
def normalize_user_id(user_id):
    return user_id if str(user_id).startswith("user_") else f"user_{user_id}"

def human_time(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%A, %d %b %Y at %I:%M %p")
    except Exception:
        return iso_str

def load_database():
    if not os.path.exists(DATABASE_JSON):
        return {}
    with open(DATABASE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def get_user_timezone(user_id):
    db = load_database()
    uid = normalize_user_id(user_id)
    return db.get(uid, {}).get("timezone", "UTC")

def load_all_tasks():
    if not os.path.exists(TASKS_CSV):
        return []
    with open(TASKS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        for r in rows:
            r.setdefault("ai_comment", "")
        return rows

def load_user_tasks(user_id, max_count=40):
    uid = normalize_user_id(user_id)
    tasks = [r for r in load_all_tasks() if r["user_id"] == uid]
    tasks_sorted = sorted(
        tasks, 
        key=lambda t: datetime.fromisoformat(t["due"]).timestamp() if t.get("due") else float("inf")
    )
    return tasks_sorted[-max_count:]  # last N tasks
