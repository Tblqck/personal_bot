# hard_starter.py

import csv
import os
import sys
import subprocess
from datetime import datetime

MOTION_CSV = "motion.csv"
FIELDS = ["engine", "status", "pid", "started_at"]

ENGINE_NAME = "reminder_engine"
ENGINE_FILE = os.path.join(os.path.dirname(__file__), "reminder_engine.py")


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

    rows = []
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
        # works on Windows and Linux
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def ensure_engine_running():

    row = read_state()

    if row and row.get("status") == "on":
        pid = row.get("pid")

        if pid and is_pid_alive(pid):
            # Already running
            return
        else:
            # stale record
            pass

    # --------------------------------------------------
    # Start engine as detached process
    # --------------------------------------------------

    creationflags = 0

    # Windows – prevent console spam
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    p = subprocess.Popen(
        [sys.executable, ENGINE_FILE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags
    )

    write_state("on", p.pid)


# Optional CLI usage
if __name__ == "__main__":
    ensure_engine_running()
