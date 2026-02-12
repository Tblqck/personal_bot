# task_utils.py
import csv
import os
import json
from datetime import datetime, timezone
import pytz

TASKS_CSV = "tasks.csv"
DATABASE_JSON = "database.json"
CSV_FIELDS = [
    "user_id",
    "title",
    "details",
    "due",
    "status",
    "google_status",
    "google_id",
    "ai_comment"
]

# -----------------------
# Helpers
# -----------------------
def normalize_user_id(user_id):
    return user_id if str(user_id).startswith("user_") else f"user_{user_id}"

# -----------------------
# Database
# -----------------------
def load_database():
    if not os.path.exists(DATABASE_JSON):
        return {}
    with open(DATABASE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def get_user_timezone(user_id):
    db = load_database()
    uid = normalize_user_id(user_id)
    return db.get(uid, {}).get("timezone", "UTC")

# -----------------------
# Task helpers
# -----------------------
def load_all_tasks():
    if not os.path.exists(TASKS_CSV):
        return []
    with open(TASKS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        for r in rows:
            r.setdefault("ai_comment", "")
        return rows

def load_user_tasks(user_id):
    uid = normalize_user_id(user_id)
    tasks = [r for r in load_all_tasks() if r["user_id"] == uid]
    def task_sort_key(t):
        try:
            dt = datetime.fromisoformat(t.get("due") or "")
            return dt.timestamp()
        except Exception:
            return float("inf")
    return sorted(tasks, key=task_sort_key)[:30]

def summarize_tasks(rows, user_timezone="UTC"):
    if not rows:
        return "You have no matching tasks."

    tz = pytz.timezone(user_timezone)
    lines = []

    for r in rows:
        title = r.get("title")
        details = r.get("details") or ""
        try:
            dt = datetime.fromisoformat(r.get("due"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(tz)
            when = dt.strftime("%A, %d %b %Y at %I:%M %p")
        except Exception:
            when = r.get("due") or "No due date"

        comment = r.get("ai_comment") or ""
        block = f"• {title}\n  → {when}"
        if details and details != "No extra details provided.":
            block += f"\n  → {details}"
        if comment:
            block += f"\n  → {comment}"
        lines.append(block)

    return "Here are your tasks:\n\n" + "\n\n".join(lines)
