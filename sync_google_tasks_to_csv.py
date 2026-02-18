# sync_google_tasks_to_csv.py

import csv
import os
import json
from datetime import datetime
import pytz

from ayth_script import list_tasks
from time_fixer import fix_time_from_text

# -----------------------
# Config
# -----------------------
TASKS_CSV = "tasks.csv"
DATABASE_FILE = os.path.join(os.path.dirname(__file__), "database.json")

FIELDS = [
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
# Ensure CSV exists
# -----------------------
def ensure_csv():
    if not os.path.exists(TASKS_CSV):
        with open(TASKS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()

# -----------------------
# Load existing CSV rows
# -----------------------
def load_existing_rows():
    ensure_csv()
    with open(TASKS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

# -----------------------
# Load user's timezone from database.json
# -----------------------
def _load_user_timezone(user_key):
    if not os.path.exists(DATABASE_FILE):
        return "UTC"
    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        return db.get(user_key, {}).get("timezone", "UTC")
    except Exception:
        return "UTC"

# -----------------------
# Parse Google due date
# -----------------------
def _parse_google_due(due_value, user_tz):
    """
    Google due may be:
    - ISO string with time
    - Date only
    - Empty
    Returns a datetime object in user timezone or None.
    """
    if not due_value:
        return None

    try:
        # ISO string
        dt = datetime.fromisoformat(due_value.replace("Z", "+00:00"))
        return dt.astimezone(user_tz)
    except Exception:
        pass

    # fallback parser using fix_time_from_text
    iso = fix_time_from_text(due_value, str(user_tz))
    if not iso:
        return None

    try:
        return datetime.fromisoformat(iso)
    except Exception:
        return None

# -----------------------
# Sync tasks for a single user
# -----------------------
def sync_user_tasks_to_csv(user_key):
    """
    Pull Google tasks for a user and append new ones to CSV.
    Only tasks scheduled today or later (user timezone) are added.
    Does NOT delete or modify existing rows.
    """
    ensure_csv()
    rows = load_existing_rows()

    existing_google_ids = {
        r.get("google_id") for r in rows if r.get("google_id")
    }

    # Load user timezone
    user_tz_name = _load_user_timezone(user_key)
    try:
        user_tz = pytz.timezone(user_tz_name)
    except Exception:
        user_tz = pytz.UTC

    now_local = datetime.now(user_tz)
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    # Fetch tasks from Google
    google_tasks = list_tasks(user_key)
    new_rows = []

    for t in google_tasks:
        google_id = t.get("id")
        if not google_id:
            continue

        # Skip already stored tasks
        if google_id in existing_google_ids:
            continue

        # Skip completed tasks on Google
        if t.get("status") == "completed":
            continue

        due_raw = t.get("due", "")
        due_dt = _parse_google_due(due_raw, user_tz)

        # Skip tasks older than today
        if due_dt and due_dt < today_start:
            continue

        new_rows.append({
            "user_id": user_key,
            "title": t.get("title", ""),
            "details": t.get("notes", "") or "",
            "due": due_raw or "",
            "status": "done",
            "google_status": "done",
            "google_id": google_id,
            "ai_comment": ""
        })

    if not new_rows:
        return 0

    with open(TASKS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writerows(new_rows)

    return len(new_rows)

# -----------------------
# Sync multiple users
# -----------------------
def sync_many_users(user_keys):
    total = 0
    for user_key in user_keys:
        try:
            added = sync_user_tasks_to_csv(user_key)
            total += added
            print(f"✅ Synced {added} tasks for {user_key}")
        except Exception as e:
            print(f"❌ Failed syncing {user_key}: {e}")
    return total

# -----------------------
# CLI test
# -----------------------
if __name__ == "__main__":
    # Example: sync a single user
    user_id = "user_7416057134"
    added_count = sync_user_tasks_to_csv(user_id)
    print(f"Total new tasks added: {added_count}")
