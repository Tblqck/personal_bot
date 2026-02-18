import os
import csv
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from openrouter import OpenRouter
import pytz

# -----------------------
# Config
# -----------------------
TASKS_CSV = "tasks.csv"
DATABASE_JSON = "database.json"
REMINDERS_LOG_CSV = "reminders_sent.csv"

# -----------------------
# Load environment
# -----------------------
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("🚨 OPENROUTER_API_KEY not found in .env")

client = OpenRouter(api_key=OPENROUTER_API_KEY)

# -----------------------
# Data loaders
# -----------------------
def load_tasks():
    if not os.path.exists(TASKS_CSV):
        return []
    with open(TASKS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        for r in rows:
            r.setdefault("google_status", "")
            r.setdefault("ai_comment", "")
        return rows

def load_user_timezones():
    if not os.path.exists(DATABASE_JSON):
        return {}
    with open(DATABASE_JSON, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {}

# -----------------------
# Daily sent check
# -----------------------
def was_daily_summary_sent(user_id, local_date):
    if not os.path.exists(REMINDERS_LOG_CSV):
        return False
    with open(REMINDERS_LOG_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if (
                r.get("user_id") == user_id
                and r.get("task_title") == "DAILY_SUMMARY"
                and r.get("local_date") == local_date
            ):
                return True
    return False

def log_daily_summary(user_id, tz_name, local_date, ai_message):
    file_exists = os.path.exists(REMINDERS_LOG_CSV)
    with open(REMINDERS_LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp_utc",
                "user_id",
                "task_title",
                "local_date",
                "user_timezone",
                "ai_message"
            ])
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            user_id,
            "DAILY_SUMMARY",
            local_date,
            tz_name,
            ai_message
        ])

# -----------------------
# Core logic
# -----------------------
def get_users_todays_tasks(tasks, user_db):
    """
    Returns:
    user_id -> {
        "timezone": pytz tz,
        "timezone_name": str,
        "tasks": [task, ...]
    }
    """
    result = {}
    for t in tasks:
        if t.get("google_status") in ["passed", "delete"]:
            continue
        if not t.get("due"):
            continue  # Skip tasks without due time

        user_id = t.get("user_id")
        if not user_id:
            continue

        user_record = user_db.get(user_id)
        if not user_record:
            continue

        tz_name = user_record.get("user_timezone")
        if not tz_name:
            continue

        try:
            tz = pytz.timezone(tz_name)
            due_utc = datetime.fromisoformat(t["due"].replace("Z", "+00:00"))
            due_local = due_utc.astimezone(tz)
            today_local = datetime.now(tz).date()
        except Exception:
            continue

        if due_local.date() != today_local:
            continue

        t["_due_local"] = due_local

        if user_id not in result:
            result[user_id] = {
                "timezone": tz,
                "timezone_name": tz_name,
                "tasks": []
            }
        result[user_id]["tasks"].append(t)

    # Sort each user's tasks by due time
    for u in result:
        result[u]["tasks"].sort(key=lambda x: x["_due_local"])
    return result

# -----------------------
# AI generator
# -----------------------
def generate_ai_daily_summary(tasks):
    lines = []
    for t in tasks:
        time_str = t["_due_local"].strftime("%H:%M")
        lines.append(f"- {time_str} — {t['title']}")
    task_block = "\n".join(lines)

    prompt = (
        "Write a short, friendly, motivating good-morning message reminding the user "
        "of the tasks they have today.\n\n"
        "Tasks:\n"
        f"{task_block}\n\n"
        "Keep it warm, concise, and very short."
    )

    try:
        completion = client.chat.send(
            model="openai/gpt-5.2",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ AI daily summary failed: {e}")
        return "Good morning! Here is what you have planned for today."

# -----------------------
# Main runner
# -----------------------
def run_daily_morning_reminder():
    tasks = load_tasks()
    user_db = load_user_timezones()
    if not tasks or not user_db:
        return

    grouped = get_users_todays_tasks(tasks, user_db)
    if not grouped:
        return

    for user_id, data in grouped.items():
        tz = data["timezone"]
        tz_name = data["timezone_name"]
        local_date = datetime.now(tz).date().isoformat()

        if was_daily_summary_sent(user_id, local_date):
            continue

        today_tasks = data["tasks"]
        if not today_tasks:
            continue

        ai_message = generate_ai_daily_summary(today_tasks)
        print(f"🌅 Daily summary for {user_id} [{tz_name}]")
        print(ai_message)

        log_daily_summary(
            user_id=user_id,
            tz_name=tz_name,
            local_date=local_date,
            ai_message=ai_message
        )

# -----------------------
# Standalone
# -----------------------
if __name__ == "__main__":
    run_daily_morning_reminder()
