# sync_google_tasks_to_csv.py

import csv
import os
import json
from datetime import datetime
import pytz

from ayth_script import list_tasks
from time_fixer import fix_time_from_text

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


def ensure_csv():
    if not os.path.exists(TASKS_CSV):
        with open(TASKS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()


def load_existing_rows():
    ensure_csv()
    with open(TASKS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_user_timezone(user_key):
    if not os.path.exists(DATABASE_FILE):
        return "UTC"

    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        return db.get(user_key, {}).get("timezone", "UTC")
    except Exception:
        return "UTC"


def _parse_google_due(due_value, user_tz):
    """
    Google due may be:
    - ISO string
    - date only
    - empty
    """
    if not due_value:
        return None

    try:
        # Already ISO
        dt = datetime.fromisoformat(due_value.replace("Z", "+00:00"))
        return dt.astimezone(user_tz)
    except Exception:
        pass

    # fallback to your own parser
    iso = fix_time_from_text(due_value, str(user_tz))
    if not iso:
        return None

    try:
        return datetime.fromisoformat(iso)
    except Exception:
        return None


def sync_user_tasks_to_csv(user_key):
    """
    Pull Google tasks for user and append new ones to CSV.
    Only tasks whose due >= now (user timezone) are added.

    Does NOT delete or modify existing rows.
    """

    ensure_csv()

    rows = load_existing_rows()

    existing_google_ids = {
        r.get("google_id")
        for r in rows
        if r.get("google_id")
    }

    user_tz_name = _load_user_timezone(user_key)

    try:
        user_tz = pytz.timezone(user_tz_name)
    except Exception:
        user_tz = pytz.UTC

    now_local = datetime.now(user_tz)

    google_tasks = list_tasks(user_key)

    new_rows = []

    for t in google_tasks:

        google_id = t.get("id")
        if not google_id:
            continue

        # skip already stored
        if google_id in existing_google_ids:
            continue

        # skip completed on Google
        if t.get("status") == "completed":
            continue

        due_raw = t.get("due", "")

        due_dt = _parse_google_due(due_raw, user_tz)

        # ---- only future / not older than now
        if due_dt and due_dt < now_local:
            continue

        new_rows.append({
            "user_id": user_key,
            "title": t.get("title", ""),
            "details": t.get("notes", "") or "",
            "due": due_raw or "",
            # ✔ aligned with your old system
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


def sync_many_users(user_keys):
    total = 0
    for user_key in user_keys:
        try:
            total += sync_user_tasks_to_csv(user_key)
        except Exception as e:
            print(f"❌ Failed syncing {user_key}: {e}")
    return total


if __name__ == "__main__":
    sync_user_tasks_to_csv("user_7416057134")
