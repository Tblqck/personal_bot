import csv
import os
import json
import threading
from datetime import datetime, date, timezone
from dotenv import load_dotenv
import openai
from difflib import SequenceMatcher

from time_fixer import fix_time_from_text
from upload_pending_tasks import upload_pending_tasks


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


# -----------------------
# Load OpenAI API Key
# -----------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not set in .env!")
openai.api_key = OPENAI_API_KEY


# -----------------------
# File paths and CSV fields
# -----------------------
TASKS_CSV = "tasks.csv"
CONTEXT_CSV = "chat_context.csv"
DATABASE_JSON = "database.json"

CSV_FIELDS = ["user_id", "title", "details", "due", "status", "google_status", "google_id", "ai_comment"]
CONTEXT_FIELDS = ["user_id", "timestamp", "role", "message"]


for file, fields in [(TASKS_CSV, CSV_FIELDS), (CONTEXT_CSV, CONTEXT_FIELDS)]:
    if not os.path.exists(file):
        with open(file, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()


# -----------------------
# Database helpers
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
# Background uploader (silent)
# -----------------------
def trigger_background_upload():
    try:
        threading.Thread(
            target=lambda: upload_pending_tasks(silent=True),
            daemon=True
        ).start()
    except Exception:
        pass


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


def save_all_tasks(rows):
    with open(TASKS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def save_task(task):
    task["user_id"] = normalize_user_id(task["user_id"])
    task["status"] = "done" if task.get("title") and task.get("due") else "pending"
    task["google_status"] = task.get("google_status") or "pending"
    task.setdefault("ai_comment", "")

    rows = load_all_tasks()
    updated = False

    for r in rows:
        ratio = SequenceMatcher(
            None,
            (r.get("title") or "").lower(),
            (task.get("title") or "").lower()
        ).ratio()

        if r["user_id"] == task["user_id"] and ratio > 0.75:
            r.update(task)
            updated = True

    if not updated:
        rows.append(task)

    save_all_tasks(rows)


def load_user_tasks(user_id):
    uid = normalize_user_id(user_id)
    tasks = [r for r in load_all_tasks() if r["user_id"] == uid]

    def task_sort_key(t):
        try:
            dt = datetime.fromisoformat(t.get("due") or "")
            return dt.timestamp()
        except Exception:
            return float("inf")

    tasks_sorted = sorted(tasks, key=task_sort_key)
    return tasks_sorted[:30]


def find_best_task_match(user_id, title):
    if not title:
        return None

    best = None
    best_ratio = 0

    for t in load_user_tasks(user_id):
        r = SequenceMatcher(
            None,
            (t.get("title") or "").lower(),
            title.lower()
        ).ratio()

        if r > best_ratio:
            best_ratio = r
            best = t

    return best if best_ratio >= 0.55 else None


# -----------------------
# Chat context helpers
# -----------------------
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

    user_rows = [r for r in rows if r["user_id"] == uid][-max_per_user:]
    rows = [r for r in rows if r["user_id"] != uid] + user_rows

    with open(CONTEXT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CONTEXT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def get_recent_context(user_id, max_age_minutes=60):
    uid = normalize_user_id(user_id)
    now = datetime.utcnow()
    out = []

    if not os.path.exists(CONTEXT_CSV):
        return out

    with open(CONTEXT_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["user_id"] != uid:
                continue

            try:
                ts = datetime.fromisoformat(r["timestamp"])
            except Exception:
                continue

            if (now - ts).total_seconds() <= max_age_minutes * 60:
                out.append({
                    "role": r["role"],
                    "content": r["message"]
                })

    return out


def cleanup_old_context(max_age_minutes=60):
    if not os.path.exists(CONTEXT_CSV):
        return

    now = datetime.utcnow()
    rows = []

    with open(CONTEXT_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                ts = datetime.fromisoformat(r["timestamp"])
            except Exception:
                continue

            if (now - ts).total_seconds() <= max_age_minutes * 60:
                rows.append(r)

    with open(CONTEXT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CONTEXT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


# -----------------------
# GPT parser
# -----------------------
def parse_message_with_gpt(message, user_id=None):

    history = get_recent_context(user_id)

    
    system_prompt = (
        "You are the core intent engine of a Telegram-based personal task assistant.\n"
        "You do NOT directly talk to users. You only return structured JSON instructions.\n"
        "\n"
        "SYSTEM ARCHITECTURE (IMPORTANT CONTEXT)\n"
        "- All tasks are stored in a local CSV file (tasks.csv).\n"
        "- tasks.csv is periodically synchronized with Google Tasks in the background.\n"
        "- A background reminder engine reads tasks.csv and queues reminders into reminders_sent.csv.\n"
        "- Another background service sends those reminders to Telegram users.\n"
        "- Conversation history is logged separately in chat_context.csv.\n"
        "- You must only decide the user's intent and task fields. Execution is handled elsewhere.\n"
        "\n"
        "YOUR RESPONSIBILITY\n"
        "- Understand the user's message and decide what action is required.\n"
        "- Extract task title, details and due time if present.\n"
        "- Never assume that a reminder is sent immediately. Reminders are handled asynchronously.\n"
        "\n"
        "Return STRICT JSON with the following keys ONLY:\n"
        "action, title, details, due, list_scope, ai_comment, response_text\n"
        "\n"
        "Allowed values for action:\n"
        "create, update, delete, list, chat\n"
        "\n"
        "ACTION RULES\n"
        "- Creating a new task = create\n"
        "- Changing the title, time, date, or details of an existing task = update\n"
        "- Cancelling, removing or dropping a task = delete\n"
        "- Asking to see tasks, summaries, or what is planned = list\n"
        "- General conversation, advice or help not tied to a task = chat\n"
        "\n"
        "IMPORTANT BEHAVIOUR RULES\n"
        "- Moving or changing the time of an existing task is ALWAYS an update.\n"
        "- If the user refers to an existing task but the exact task is unclear, still use update and describe the intent in ai_comment.\n"
        "- If a due time or date is mentioned, always populate the due field using ISO 8601 format if possible.\n"
        "- If the user does not clearly specify a due time, leave the due field as null.\n"
        "- If the user does not clearly specify a title, leave the title field as null.\n"
        "- Never invent task titles, dates or times.\n"
        "\n"
        "LIST SCOPE RULES\n"
        "- list_scope may be one of: all, today, tomorrow, upcoming, overdue.\n"
        "- If the user does not specify a scope, use \"all\".\n"
        "\n"
        "ai_comment RULE\n"
        "- Put short helpful hints, clarifications, or advice here.\n"
        "- This field may be empty but must always exist.\n"
        "- Do NOT place operational instructions here.\n"
        "\n"
        "response_text RULE\n"
        "- Write a short, natural confirmation or chat reply for the user.\n"
        "- Do not mention CSV files, background jobs, Google APIs or internal architecture.\n"
        "- Do not mention that you are returning JSON.\n"
        "\n"
        "CRITICAL OUTPUT RULE\n"
        "- Output ONLY valid JSON.\n"
        "- Do not wrap it in markdown.\n"
        "- Do not include any explanation outside the JSON object."
    )

    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": message}]
    )

    try:
        resp = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.2
        )

        content = resp.choices[0].message.content.strip()
        start = content.find("{")
        end = content.rfind("}") + 1
        result = json.loads(content[start:end])

    except Exception:
        result = {
            "action": "chat",
            "title": None,
            "details": None,
            "due": None,
            "list_scope": None,
            "ai_comment": "",
            "response_text": "Sorry, I didn't get that."
        }

    for k in ["action", "title", "details", "due", "list_scope", "ai_comment", "response_text"]:
        result.setdefault(k, "" if k == "ai_comment" else None)

    if result.get("due") and user_id:
        tz = get_user_timezone(user_id)
        try:
            fixed = fix_time_from_text(result["due"], user_timezone=tz)
            if fixed:
                result["due"] = fixed
        except Exception:
            pass

    return result


# -----------------------
# Main AI callable
# -----------------------
def ai_thought(user_id, message):

    cleanup_old_context()
    save_chat_context(user_id, "user", message)

    result = parse_message_with_gpt(message, user_id)
    action = result.get("action", "chat")
    reply = result.get("response_text", "Okay.")

    if action in ["create", "update", "delete", "list"]:

        tasks = load_user_tasks(user_id)

        if action == "list":

            key = (result.get("title") or "").lower()
            if key:
                tasks = [t for t in tasks if key in (t.get("title") or "").lower()]

            scope = result.get("list_scope") or "all"
            today = date.today()

            filtered = []

            for t in tasks:
                try:
                    dt = datetime.fromisoformat(t["due"])
                except Exception:
                    continue

                if scope == "today" and dt.date() == today:
                    filtered.append(t)
                elif scope == "calls" and "call" in (t.get("title") or "").lower():
                    filtered.append(t)
                elif scope == "all":
                    filtered.append(t)

            reply = summarize_tasks(filtered)

        elif action == "delete":

            target = find_best_task_match(user_id, result.get("title"))

            if target:
                rows = load_all_tasks()

                for r in rows:
                    if r["user_id"] == target["user_id"] and r["title"] == target["title"]:
                        r["google_status"] = "delete"

                save_all_tasks(rows)
                trigger_background_upload()

                reply = f"Deleted: {target['title']}"

        elif action == "update":

            target = find_best_task_match(user_id, result.get("title"))

            if target:
                rows = load_all_tasks()

                for r in rows:
                    if r["user_id"] == target["user_id"] and r["title"] == target["title"]:

                        if result.get("due"):
                            r["due"] = result["due"]

                        if result.get("details"):
                            r["details"] = result["details"]

                        if result.get("ai_comment"):
                            r["ai_comment"] = result["ai_comment"]

                        r["google_status"] = "pending"
                        r["status"] = "done"

                save_all_tasks(rows)
                trigger_background_upload()

                reply = f"Updated: {target['title']}"

        elif action == "create":

            ready = bool(result.get("title") and result.get("due"))

            task = {
                "user_id": normalize_user_id(user_id),
                "title": result.get("title"),
                "details": result.get("details") or "No extra details provided.",
                "due": result.get("due"),
                "status": "done" if ready else "pending",
                "google_status": "pending",
                "google_id": "",
                "ai_comment": result.get("ai_comment") or ""
            }

            save_task(task)

            if ready:
                trigger_background_upload()

            reply = result.get("response_text") or "Task saved."

    save_chat_context(user_id, "assistant", reply)
    return reply


# -----------------------
# Task summarizer
# -----------------------
def summarize_tasks(rows):

    if not rows:
        return "You have no matching tasks."

    lines = []

    for r in rows:
        title = r.get("title")
        details = r.get("details") or ""
        when = human_time(r.get("due"))
        comment = r.get("ai_comment") or ""

        block = f"• {title}\n  → {when}"

        if details and details != "No extra details provided.":
            block += f"\n  → {details}"

        if comment:
            block += f"\n  → {comment}"

        lines.append(block)

    return "Here are your tasks:\n\n" + "\n\n".join(lines)
