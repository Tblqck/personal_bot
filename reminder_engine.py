# reminder_engine.py
import os
import csv
import json
import time
import pytz
from datetime import datetime, timedelta
from upload_pending_tasks import upload_pending_tasks
from intent_engine import ai_thought
from telegram import Bot

# --- Configuration ---
TASKS_CSV = "tasks.csv"
USERS_DB = "database.json"
CSV_FIELDS = ["user_id", "title", "details", "due", "status", "google_status", "google_id", "ai_comment"]

REMINDER_INTERVALS = [30, 10, 1]  # minutes before due time
MORNING_HOUR = 6  # 6 AM local time
CHECK_INTERVAL = 60  # seconds
BOT_TOKEN = os.getenv("BOT_TOKEN2")
bot = Bot(token=BOT_TOKEN)

# --- Helper functions ---
def load_users():
    if not os.path.exists(USERS_DB):
        return {}
    with open(USERS_DB, "r", encoding="utf-8") as f:
        return json.load(f)

def load_tasks():
    if not os.path.exists(TASKS_CSV):
        return []
    with open(TASKS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        for r in rows:
            if "ai_comment" not in r:
                r["ai_comment"] = ""
        return rows

def save_tasks(rows):
    with open(TASKS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

def human_time(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%A, %d %b %Y at %I:%M %p")
    except Exception:
        return iso_str

# --- Reminder state ---
sent_reminders = {}  # user_id -> {task_key -> [intervals_sent]}

# --- Telegram message sender ---
def send_message(user_id, text):
    try:
        bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        print(f"❌ Failed to send message to {user_id}: {e}")

# --- Morning summary ---
def send_morning_summary(user_id, tasks):
    if not tasks:
        return

    message_lines = ["🌅 Good morning! Here’s your schedule for today:\n"]

    for t in tasks:
        due = human_time(t["due"])
        details = t.get("details") or ""
        ai_comment = t.get("ai_comment") or ""

        block = f"• {t['title']}\n  → {due}"
        if details:
            block += f"\n  → {details}"
        if ai_comment:
            block += f"\n  → {ai_comment}"

        message_lines.append(block)

    send_message(user_id, "\n\n".join(message_lines))


# --- Smart continuous reminders ---
def check_and_send_reminders():
    users = load_users()
    tasks = load_tasks()

    now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)

    rows_updated = False

    for user_id, info in users.items():
        tz_name = info.get("timezone", "UTC")

        try:
            user_tz = pytz.timezone(tz_name)
        except Exception:
            user_tz = pytz.utc

        now = now_utc.astimezone(user_tz)

        # ---- Morning summary (run once per day per user)
        if now.hour == MORNING_HOUR and now.minute == 0:
            today_tasks = [
                t for t in tasks
                if t["user_id"] == str(user_id)
                and t["google_status"] not in ["passed", "delete"]
            ]

            send_morning_summary(user_id, today_tasks)

            sent_reminders.setdefault(user_id, {})
            for t in today_tasks:
                task_key = make_task_key(t)
                sent_reminders[user_id][task_key] = []

        # ---- Per task reminders
        for t in tasks:
            if t["user_id"] != str(user_id):
                continue

            if t["google_status"] in ["passed", "delete"]:
                continue

            if not t.get("due"):
                continue

            try:
                due_dt = datetime.fromisoformat(
                    t["due"].replace("Z", "+00:00")
                )

                if due_dt.tzinfo is None:
                    due_dt = pytz.utc.localize(due_dt)

                due_local = due_dt.astimezone(user_tz)

            except Exception:
                continue

            task_key = make_task_key(t)

            # ---- passed
            if now >= due_local:
                if t["google_status"] != "passed":
                    t["google_status"] = "passed"
                    rows_updated = True
                    print(f"✅ Task '{t['title']}' passed for {user_id}")
                continue

            minutes_left = (due_local - now).total_seconds() / 60

            sent_intervals = sent_reminders \
                .setdefault(user_id, {}) \
                .setdefault(task_key, [])

            for interval in REMINDER_INTERVALS:
                # IMPORTANT FIX:
                # only fire when we cross the window
                if (
                    interval not in sent_intervals
                    and minutes_left <= interval
                    and minutes_left > interval - 1
                ):
                    send_message(
                        user_id,
                        f"⏰ Reminder: '{t['title']}' is due in {int(minutes_left)} minutes.\n"
                        f"{t.get('ai_comment','')}"
                    )
                    sent_intervals.append(interval)

    if rows_updated:
        save_tasks(tasks)
        upload_pending_tasks()


def make_task_key(t):
    # stable key even if titles repeat
    return f"{t.get('google_id','')}|{t.get('title','')}|{t.get('due','')}"


# --- Scheduler loop ---
def run_reminder_loop():
    print("🕒 Reminder engine running...")
    while True:
        try:
            check_and_send_reminders()
        except Exception as e:
            print(f"❌ Error in reminder loop: {e}")
        time.sleep(CHECK_INTERVAL)


# --------------------------------------------------
# Public entry for hard_starter.py
# --------------------------------------------------
def run_forever():
    run_reminder_loop()


# --- Direct run support ---
if __name__ == "__main__":
    run_forever()
