# hard_starter.py

import os
import csv
from datetime import datetime, timezone
from dotenv import load_dotenv
from openrouter import OpenRouter

# -----------------------
# Config
# -----------------------

TASKS_CSV = "tasks.csv"

# ✅ renamed (this is the QUEUE, not the sent log)
REMINDERS_QUEUE_CSV = "reminders_queue.csv"

# ✅ use list, not set (deterministic order)
REMINDER_MINUTES = [30, 10, 1]

WINDOW_SECONDS = 30   # allow small clock drift (±30s)

# -----------------------
# Env / client
# -----------------------

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env")

client = OpenRouter(api_key=OPENROUTER_API_KEY)


# -----------------------
# CSV helpers
# -----------------------

def load_tasks():
    if not os.path.exists(TASKS_CSV):
        return []

    with open(TASKS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        r.setdefault("ai_comment", "")
        r.setdefault("google_status", "")

    return rows


def save_tasks(rows):
    if not rows:
        return

    fieldnames = rows[0].keys()

    with open(TASKS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_existing_queue_keys():
    if not os.path.exists(REMINDERS_QUEUE_CSV):
        return set()

    with open(REMINDERS_QUEUE_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    keys = set()
    for r in rows:
        k = f"{r.get('user_id')}|{r.get('task_key')}|{r.get('due')}|{r.get('trigger_minute')}"
        keys.add(k)

    return keys


def append_to_queue(row):
    fieldnames = [
        "timestamp_utc",
        "user_id",
        "task_key",
        "task_title",
        "due",
        "minutes_left",
        "trigger_minute",
        "ai_message"
    ]

    file_exists = os.path.exists(REMINDERS_QUEUE_CSV)

    with open(REMINDERS_QUEUE_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# -----------------------
# Core logic
# -----------------------

def generate_ai_reminder(task_title, ai_comment="", minutes_left=None):

    prompt = (
        "Write one short, natural and friendly reminder sentence for this task.\n"
        "Do not use markdown, stars, quotes or emojis.\n"
        f"Task: {task_title}"
    )

    if ai_comment:
        prompt += "\nExtra note: " + ai_comment

    if minutes_left is not None:
        if minutes_left <= 1:
            prompt += "\nIt is due in one minute."
        else:
            prompt += f"\nIt is due in {int(minutes_left)} minutes."

    try:
        completion = client.chat.send(
            model="openai/gpt-5.2",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )

        text = completion.choices[0].message.content.strip()
        return text.replace("*", "").replace("_", "").replace("`", "")

    except Exception as e:
        print("AI reminder generation failed:", e)
        return f"Friendly reminder: {task_title}"


def should_trigger(minutes_left, target_minute):
    target_seconds = target_minute * 60
    current_seconds = int(minutes_left * 60)

    return abs(current_seconds - target_seconds) <= WINDOW_SECONDS


# -----------------------
# Main producer
# -----------------------

def run_reminder_ai():

    tasks = load_tasks()
    existing_keys = load_existing_queue_keys()

    now = datetime.now(timezone.utc)

    produced = 0
    tasks_changed = False

    for task in tasks:

        if task.get("google_status") in ("passed", "delete"):
            continue

        if not task.get("due"):
            continue

        try:
            due_dt = datetime.fromisoformat(
                task["due"].replace("Z", "+00:00")
            )
        except Exception:
            continue

        # -------------------
        # mark passed tasks
        # -------------------
        if due_dt <= now:
            if task.get("google_status") != "passed":
                task["google_status"] = "passed"
                tasks_changed = True
            continue

        user_id = task.get("user_id")
        if not user_id:
            continue

        minutes_left = (due_dt - now).total_seconds() / 60

        # -------------------
        # only 30, 10, 1 min
        # -------------------
        trigger_minute = None
        for m in REMINDER_MINUTES:
            if should_trigger(minutes_left, m):
                trigger_minute = m
                break

        if trigger_minute is None:
            continue

        task_key = task.get("google_id") or task.get("title")

        dedup_key = (
            f"{user_id}|{task_key}|{task.get('due')}|{trigger_minute}"
        )

        if dedup_key in existing_keys:
            continue

        ai_message = generate_ai_reminder(
            task.get("title", ""),
            task.get("ai_comment", ""),
            minutes_left
        )

        append_to_queue({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "task_key": task_key,
            "task_title": task.get("title", ""),
            "due": task.get("due", ""),
            "minutes_left": int(round(minutes_left)),
            "trigger_minute": trigger_minute,
            "ai_message": ai_message
        })

        existing_keys.add(dedup_key)
        produced += 1

        print(
            f"Queued {trigger_minute}min reminder for {user_id} -> {task.get('title')}"
        )

    if tasks_changed:
        save_tasks(tasks)
        print("Updated passed tasks in tasks.csv")

    print(f"Produced {produced} reminder(s).")


if __name__ == "__main__":
    run_reminder_ai()
