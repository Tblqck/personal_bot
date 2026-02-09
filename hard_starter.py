import csv
import os
import sys
import subprocess
from datetime import datetime, timedelta
import time
import threading

from sync_google_tasks_to_csv import sync_user_tasks_to_csv

MOTION_CSV = "motion.csv"
FIELDS = ["engine", "status", "pid", "started_at"]
ENGINE_NAME = "reminder_engine"
ENGINE_FILE = os.path.join(os.path.dirname(__file__), "reminder_engine.py")

DATABASE_FILE = os.path.join(os.path.dirname(__file__), "database.json")  # user DB


# ----------------------
# Motion CSV helpers
# ----------------------
def ensure_motion_file():
    if not os.path.exists(MOTION_CSV):
        with open(MOTION_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()


def read_state():
    ensure_motion_file()
    with open(MOTION_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if r.get("engine") == ENGINE_NAME:
            return r
    return None


def write_state(status, pid):
    ensure_motion_file()
    with open(MOTION_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if r.get("engine") != ENGINE_NAME]
    rows.append({
        "engine": ENGINE_NAME,
        "status": status,
        "pid": str(pid or ""),
        "started_at": datetime.utcnow().isoformat()
    })
    with open(MOTION_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def is_pid_alive(pid):
    try:
        pid = int(pid)
    except Exception:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


# ----------------------
# Start reminder engine
# ----------------------
def start_reminder_engine():
    row = read_state()
    if row and row.get("status") == "on":
        pid = row.get("pid")
        if pid and is_pid_alive(pid):
            return  # already running

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    p = subprocess.Popen(
        [sys.executable, ENGINE_FILE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags
    )
    write_state("on", p.pid)


# ----------------------
# Daily Google Task Sync
# ----------------------
def daily_google_task_sync():
    """
    Runs once per day at 00:00 user local time for all users in DB.
    """
    while True:
        now = datetime.now()
        # next run is today at 00:00 or tomorrow if already passed
        next_run = datetime.combine(now.date(), datetime.min.time())
        if now >= next_run:
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()
        time.sleep(wait_seconds)  # sleep until next run

        try:
            # load all users
            import json
            if os.path.exists(DATABASE_FILE):
                with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                    db = json.load(f)
            else:
                db = {}

            for user_key in db.keys():
                try:
                    count = sync_user_tasks_to_csv(user_key)
                    print(f"✅ Synced {count} tasks for {user_key}")
                except Exception as e:
                    print(f"❌ Failed to sync {user_key}: {e}")

        except Exception as e:
            print(f"❌ Daily sync error: {e}")


# ----------------------
# Ensure engine + schedule daily sync
# ----------------------
def ensure_engine_running():
    start_reminder_engine()
    # start daily sync in background
    t = threading.Thread(target=daily_google_task_sync, daemon=True)
    t.start()


# ----------------------
# CLI usage
# ----------------------
if __name__ == "__main__":
    ensure_engine_running()
    # keep process alive
    while True:
        time.sleep(60)
