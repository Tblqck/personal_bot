# intent_engine.py

import os
import threading
from datetime import datetime
import pytz
import csv
from difflib import SequenceMatcher

from upload_pending_tasks import upload_pending_tasks
from ensemble import get_ensemble_response
from task_utils import (
    load_user_tasks,
    get_user_timezone,
    summarize_tasks,
    normalize_user_id,
    load_all_tasks,
    CSV_FIELDS,
    TASKS_CSV
)

# -----------------------
# Background uploader
# -----------------------

def trigger_background_upload():
    t = threading.Thread(
        target=upload_pending_tasks,
        kwargs={"silent": True},
        daemon=True
    )
    t.start()


# -----------------------
# Chat context helpers
# -----------------------

CONTEXT_CSV = "chat_context.csv"
CONTEXT_FIELDS = ["user_id", "timestamp", "role", "message"]


def save_chat_context(user_id, role, message, max_per_user=40):
    uid = normalize_user_id(user_id)
    timestamp = datetime.utcnow().isoformat()

    rows = []

    if os.path.exists(CONTEXT_CSV):
        with open(CONTEXT_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    rows.append({
        "user_id": uid,
        "timestamp": timestamp,
        "role": role,
        "message": message
    })

    user_rows = [r for r in rows if r.get("user_id") == uid][-max_per_user:]
    rows = [r for r in rows if r.get("user_id") != uid] + user_rows

    with open(CONTEXT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CONTEXT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def load_chat_context(user_id, max_per_user=40):
    if not os.path.exists(CONTEXT_CSV):
        return []

    uid = normalize_user_id(user_id)

    rows = []
    with open(CONTEXT_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("user_id") == uid:
                rows.append(r)

    return rows[-max_per_user:]


# -----------------------
# Task helpers
# -----------------------

def _normalize_task_row(row):
    clean = {f: "" for f in CSV_FIELDS}
    clean.update(row)

    clean["user_id"] = normalize_user_id(clean.get("user_id"))
    clean["title"] = clean.get("title") or ""
    clean["details"] = clean.get("details") or ""
    clean["due"] = clean.get("due") or ""
    clean["google_id"] = clean.get("google_id") or ""
    clean["ai_comment"] = clean.get("ai_comment") or ""
    clean["google_status"] = clean.get("google_status") or "pending"

    if clean.get("title") and clean.get("due"):
        clean["status"] = "done"
    else:
        clean["status"] = clean.get("status") or "pending"

    return clean


def save_task(task):
    task = _normalize_task_row(task)

    rows = load_all_tasks()
    updated = False

    for r in rows:
        same_user = normalize_user_id(r.get("user_id")) == task["user_id"]

        old_title = (r.get("title") or "").lower()
        new_title = (task.get("title") or "").lower()
        ratio = SequenceMatcher(None, old_title, new_title).ratio()

        same_google_id = (
            task.get("google_id")
            and r.get("google_id") == task.get("google_id")
        )

        if same_user and (same_google_id or ratio > 0.75):
            r.update(task)
            r["google_status"] = "pending"
            updated = True
            break

    if not updated:
        rows.append(task)

    rows = [_normalize_task_row(r) for r in rows]

    with open(TASKS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def mark_task_for_delete(user_id, google_id):
    uid = normalize_user_id(user_id)

    rows = load_all_tasks()
    found = False

    for r in rows:
        if (
            normalize_user_id(r.get("user_id")) == uid
            and r.get("google_id") == google_id
        ):
            r["google_status"] = "delete"
            found = True
            break

    if found:
        rows = [_normalize_task_row(r) for r in rows]

        with open(TASKS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    return found


# -----------------------
# Main AI thought
# -----------------------

def ai_thought(user_id, message):
    save_chat_context(user_id, "user", message)

    user_context = load_chat_context(user_id, 40)
    tasks = load_user_tasks(user_id)[:40]

    user_tz = get_user_timezone(user_id)
    now = datetime.now(pytz.timezone(user_tz))

    packet = {
        "user_id": user_id,
        "user_message": message,
        "chat_context": user_context,
        "tasks": tasks,
        "user_timezone": user_tz,
        "current_time": now.isoformat()
    }

    result = get_ensemble_response(packet) or {}

    action = result.get("action", "chat")

    # -------- FIX (only change) --------
    response_text = result.get("response_text") or ""
    # ----------------------------------

    # ---------------- CREATE ----------------
    if action == "create":
        params = result.get("parameters") or {}

        task = {
            "user_id": user_id,
            "title": params.get("title"),
            "details": params.get("details"),
            "due": params.get("due"),
            "google_status": "pending",
            "google_id": "",
            "ai_comment": result.get("ai_comment", "")
        }

        if task["title"] or task["due"]:
            save_task(task)
            trigger_background_upload()

        reply = response_text

    # ---------------- UPDATE ----------------
    elif action == "update":
        params = result.get("parameters") or {}
        google_id = params.get("google_id")

        reply = response_text

        if google_id:
            rows = load_all_tasks()
            updated = False

            for r in rows:
                if (
                    normalize_user_id(r.get("user_id")) == normalize_user_id(user_id)
                    and r.get("google_id") == google_id
                ):
                    for k in ("title", "details", "due"):
                        if params.get(k) is not None:
                            r[k] = params[k]

                    if "ai_comment" in result:
                        r["ai_comment"] = result["ai_comment"]

                    r["google_status"] = "pending"
                    updated = True
                    break

            if updated:
                rows = [_normalize_task_row(r) for r in rows]

                with open(TASKS_CSV, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                    writer.writeheader()
                    writer.writerows(rows)

                trigger_background_upload()

    # ---------------- DELETE ----------------
    elif action == "delete":
        params = result.get("parameters") or {}
        google_id = params.get("google_id")

        reply = response_text

        if google_id:
            deleted = mark_task_for_delete(user_id, google_id)
            if deleted:
                trigger_background_upload()

    # ---------------- LIST ----------------
    elif action == "list":
        params = result.get("parameters") or {}
        google_ids = params.get("google_ids", [])

        all_tasks = load_user_tasks(user_id)

        if google_ids:
            idset = set(google_ids)
            filtered = [t for t in all_tasks if t.get("google_id") in idset]
        else:
            filtered = []

        reply = summarize_tasks(filtered, user_timezone=user_tz)

    # ---------------- CHAT / DEFAULT ----------------
    else:
        reply = response_text or "Okay."

    save_chat_context(user_id, "assistant", reply)
    return reply
