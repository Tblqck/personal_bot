# reminder_engine_openrouter.py
import os
import csv
from datetime import datetime, timezone
from dotenv import load_dotenv
from openrouter import OpenRouter

# --- Load environment ---
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("🚨 OPENROUTER_API_KEY not found in .env")

# Initialize OpenRouter client
client = OpenRouter(api_key=OPENROUTER_API_KEY)

TASKS_CSV = "tasks.csv"
REMINDERS_LOG_CSV = "reminders_sent.csv"


# --- Helpers ---
def load_tasks():
    if not os.path.exists(TASKS_CSV):
        return []
    with open(TASKS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        for r in rows:
            r.setdefault("ai_comment", "")
            r.setdefault("google_status", "")
        return rows


def get_next_task_per_user(tasks):
    """Return a dict: user_id -> next upcoming task (soonest due)."""
    now = datetime.now(timezone.utc)
    user_tasks = {}
    for t in tasks:
        if t.get("google_status") in ["passed", "delete"]:
            continue
        if not t.get("due"):
            continue
        try:
            due_dt = datetime.fromisoformat(t["due"].replace("Z", "+00:00"))
        except Exception:
            continue
        if due_dt < now:
            continue
        user_id = t["user_id"]
        if user_id not in user_tasks or due_dt < user_tasks[user_id]["due_dt"]:
            t["due_dt"] = due_dt
            user_tasks[user_id] = t
    return user_tasks


def generate_ai_reminder(task_title, ai_comment=""):
    """Generate a personalized reminder using OpenRouter."""
    prompt = (
        f"Write a short, friendly, personalized reminder for the task: '{task_title}'. "
        f"{ai_comment}"
    )
    try:
        completion = client.chat.send(
            model="openai/gpt-5.2",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        message = completion.choices[0].message.content.strip()
        return message
    except Exception as e:
        print(f"❌ AI reminder generation failed: {e}")
        return f"Reminder: {task_title}"  # fallback


def log_reminder(user_id, task_title, ai_message, minutes_left):
    """Append reminder info to CSV."""
    file_exists = os.path.exists(REMINDERS_LOG_CSV)
    with open(REMINDERS_LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp_utc", "user_id", "task_title", "minutes_left", "ai_message"])
        writer.writerow([datetime.now(timezone.utc).isoformat(), user_id, task_title, int(minutes_left), ai_message])


# --- Main reminder logic ---
def run_reminder_ai():
    tasks = load_tasks()
    next_tasks = get_next_task_per_user(tasks)
    now = datetime.now(timezone.utc)

    if not next_tasks:
        print("No upcoming tasks found.")
        return

    for user_id, task in next_tasks.items():
        due_dt = task["due_dt"]
        minutes_left = (due_dt - now).total_seconds() / 60

        # Generate personalized AI reminder using OpenRouter
        ai_message = generate_ai_reminder(task["title"], task.get("ai_comment", ""))

        # Print and log
        print(f"⏰ {user_id}: {ai_message} (due in {int(minutes_left)} min)")
        log_reminder(user_id, task["title"], ai_message, minutes_left)


# --- Standalone run ---
if __name__ == "__main__":
    run_reminder_ai()
