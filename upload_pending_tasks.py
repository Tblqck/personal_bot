# upload_pending_tasks.py
import csv
import os
import json
from datetime import datetime
import pytz

from ayth_script import create_task, update_task, delete_task, complete_task
from time_fixer import fix_time_from_text
from time_fixer_ai import fix_time_with_model

TASKS_CSV = "tasks.csv"
USERS_DB = "database.json"
CSV_FIELDS = ["user_id", "title", "details", "due", "status", "google_status", "google_id", "ai_comment"]

TEST_MODE = False  # set True to skip Google API calls for testing


# ----------------------------
# small logger helper
# ----------------------------
def log(msg, silent):
    if not silent:
        print(msg)


# ----------------------------
# Get user info (timezone)
# ----------------------------
def get_user_info(user_id, default_timezone="UTC"):
    if not os.path.exists(USERS_DB):
        return {"timezone": default_timezone}
    try:
        with open(USERS_DB, "r", encoding="utf-8") as f:
            db = json.load(f)
        return db.get(user_id, {"timezone": default_timezone})
    except Exception:
        return {"timezone": default_timezone}


# ----------------------------
# Fix due date
# ----------------------------
def fix_due(due_str, user_tz):
    """
    Returns a valid ISO timestamp for the task.
    Uses time_fixer first, then time_fixer_ai as fallback.
    """
    if due_str:
        fixed_due = fix_time_from_text(due_str, user_timezone=user_tz)
        if fixed_due:
            return fixed_due
    return fix_time_with_model(due_str, user_timezone=user_tz)


# ----------------------------
# Main function
# ----------------------------
def upload_pending_tasks(silent=False):

    if not os.path.exists(TASKS_CSV):
        log("tasks.csv not found.", silent)
        return

    updated_any = False

    with open(TASKS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    new_rows = []

    for row in rows:
        user_id = row.get("user_id")
        title = row.get("title")
        details = row.get("details")
        due = row.get("due")
        status = row.get("status")
        google_status = row.get("google_status")
        google_id = row.get("google_id")

        if not user_id or not title:
            log(f"⚠️ Skipping incomplete task: {row}", silent)
            new_rows.append(row)
            continue

        tz = get_user_info(user_id).get("timezone", "UTC")

        # ----------------------------
        # Fix invalid or missing due
        # ----------------------------
        due_dt = None
        try:
            if due:
                due_dt = datetime.fromisoformat(due)
        except Exception:
            due_dt = None

        if not due_dt:
            fixed_due = fix_due(due, tz)
            if fixed_due:
                row["due"] = fixed_due
                due = fixed_due
                try:
                    due_dt = datetime.fromisoformat(due)
                except Exception:
                    due_dt = None

        try:
            # ----------------------------
            # DELETE tasks
            # ----------------------------
            if google_status == "delete" and google_id:
                if not TEST_MODE:
                    log(f"🗑 Deleting task {title} ({google_id}) for {user_id}", silent)
                    delete_task(google_id, user_id)
                    updated_any = True

                log(f"✅ Deleted task removed from CSV: {title}", silent)
                continue

            # ----------------------------
            # COMPLETE tasks ("passed")
            # ----------------------------
            elif google_status == "passed" and google_id:
                if not TEST_MODE:
                    log(f"✅ Completing task {title} ({google_id}) for {user_id}", silent)
                    complete_task(google_id, user_id)
                    updated_any = True

                log(f"✅ Task completed and removed from CSV: {title}", silent)
                continue

            # ----------------------------
            # PENDING tasks → upload / update
            # ----------------------------
            elif google_status == "pending":

                if google_id:
                    if not TEST_MODE:
                        log(f"🔄 Updating task {title} ({google_id}) for {user_id}", silent)

                        resp = update_task(
                            google_id,
                            user_id,
                            title=title,
                            details=details,
                            due=due
                        )

                        if resp.get("id"):
                            row["google_status"] = "done"
                            updated_any = True
                            log(f"✅ Updated task (Google ID: {resp['id']})", silent)
                        else:
                            log(f"❌ Update failed: {resp}", silent)

                else:
                    if not TEST_MODE:
                        log(f"⬆ Uploading new task for {user_id}: {title}", silent)

                        resp = create_task(
                            title=title,
                            due=due,
                            user_key=user_id,
                            details=details
                        )

                        if resp.get("id"):
                            row["google_status"] = "done"
                            row["google_id"] = resp["id"]
                            updated_any = True
                            log(f"✅ Uploaded task (Google ID: {resp['id']})", silent)

                new_rows.append(row)

            # ----------------------------
            # DONE tasks
            # ----------------------------
            elif google_status == "done":
                new_rows.append(row)

            else:
                new_rows.append(row)

        except Exception as e:
            log(f"❌ Error processing task '{title}' for {user_id}: {e}", silent)
            new_rows.append(row)

    # ----------------------------
    # Save CSV
    # ----------------------------
    with open(TASKS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(new_rows)

    if updated_any:
        log("\n✔ tasks.csv synced and cleaned.", silent)
    else:
        log("\nNothing updated.", silent)


# ----------------------------
# CLI entry
# ----------------------------
if __name__ == "__main__":
    upload_pending_tasks()
