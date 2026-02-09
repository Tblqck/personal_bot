# muster_point.py

import json
import difflib

from config import DATABASE_FILE
from ayth_script import (
    create_task,
    list_tasks,
    update_task,
    delete_task,
    complete_task,
    generate_auth_url,
    register_user_via_url,
    register_user_timezone_first
)

from intent_engine import ai_thought
from sync_google_tasks_to_csv import sync_user_tasks_to_csv

# -------------------------------------------------
# In-memory states
# -------------------------------------------------
conversation_state = {}      # user_key -> frame state
onboarding_pending = {}      # user_key -> True
timezone_pending = {}        # user_key -> True

# -------------------------------------------------
# Main entry point
# -------------------------------------------------
def handle_user_message(user_id, message_text):

    user_key = f"user_{user_id}"

    # -------------------------------------------------
    # Load DB
    # -------------------------------------------------
    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
    except FileNotFoundError:
        db = {}

    # -------------------------------------------------
    # STEP 0 – timezone onboarding (NON BLOCKING)
    # -------------------------------------------------
    if user_key in timezone_pending:

        tz_text = message_text.strip()
        try:
            tz = register_user_timezone_first(user_key, tz_text)
        except TypeError:
            tz = register_user_timezone_first(user_key, tz_text)

        timezone_pending.pop(user_key, None)

        return {
            "status": "ok",
            "message": (
                f"Timezone set to **{tz}**.\n\n"
                "Now connect your Google Tasks account using /connect."
            )
        }

    if user_key not in db or "timezone" not in db.get(user_key, {}):
        timezone_pending[user_key] = True
        return {
            "status": "awaiting",
            "next_slot": "timezone",
            "message": (
                "Please enter your timezone.\n"
                "Example: Africa/Lagos"
            )
        }

    # -------------------------------------------------
    # Step 1: /connect onboarding
    # -------------------------------------------------
    if message_text.strip().lower() == "/connect":
        auth_url = generate_auth_url()
        onboarding_pending[user_key] = True
        return {
            "status": "ok",
            "message": (
                "Connect your Google Tasks account (one-time setup)\n\n"
                f"Open this link in your browser:\n{auth_url}\n\n"
                "> Follow the steps on-screen to authorize the bot."
            )
        }

    # -------------------------------------------------
    # Step 2: OAuth redirect URL handling
    # -------------------------------------------------
    if onboarding_pending.get(user_key):

        if "http" not in message_text.lower():
            return {
                "status": "awaiting",
                "message": "Please paste the full redirect URL from your browser."
            }

        try:
            register_user_via_url(
                user_key=user_key,
                full_url=message_text.strip()
            )

            # Immediately sync Google Tasks for this user
            try:
                count = sync_user_tasks_to_csv(user_key)
            except Exception as e:
                print(f"❌ Failed to sync tasks immediately for {user_key}: {e}")
                count = 0

            onboarding_pending.pop(user_key, None)

            return {
                "status": "ok",
                "message": (
                    f"✅ Google Tasks account connected successfully!\n"
                    f"🗂 {count} tasks synced from Google Tasks."
                )
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"❌ Failed to complete setup: {str(e)}"
            }

    # -------------------------------------------------
    # Step 3: Slot filling (creating/updating tasks)
    # -------------------------------------------------
    if user_key in conversation_state:

        state = conversation_state[user_key]
        frame = state["frame"]
        awaiting = state.get("awaiting")

        if awaiting:
            frame[awaiting] = message_text.strip()
            state["awaiting"] = None

        if not frame.get("title"):
            state["awaiting"] = "title"
            return {
                "status": "awaiting",
                "next_slot": "title",
                "message": "❓ What is the task title?"
            }

        if not frame.get("due"):
            state["awaiting"] = "due"
            return {
                "status": "awaiting",
                "next_slot": "due",
                "message": "❓ When should this task be done?"
            }

        try:
            existing_tasks = list_tasks(user_key)
            similar_task = None

            for task in existing_tasks:
                ratio = difflib.SequenceMatcher(
                    None,
                    task["title"].lower(),
                    frame["title"].lower()
                ).ratio()
                if ratio > 0.75:
                    similar_task = task
                    break

            if similar_task:
                update_task(
                    task_id=similar_task["id"],
                    title=frame["title"],
                    due=frame["due"],
                    details=frame.get("details"),
                    user_key=user_key
                )
                conversation_state.pop(user_key, None)
                return {
                    "status": "ok",
                    "message": f"🔄 Updated task **{frame['title']}**."
                }

            create_task(
                title=frame["title"],
                due=frame["due"],
                details=frame.get("details"),
                user_key=user_key
            )
            conversation_state.pop(user_key, None)
            return {
                "status": "ok",
                "message": f"✅ Task **{frame['title']}** scheduled."
            }

        except Exception as e:
            conversation_state.pop(user_key, None)
            return {
                "status": "error",
                "message": f"❌ Failed to save task: {str(e)}"
            }

    # -------------------------------------------------
    # Step 4: AI intent parsing (fallback)
    # -------------------------------------------------
    try:
        reply = ai_thought(user_id, message_text)
        return {
            "status": "ok",
            "message": reply
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ Something went wrong: {str(e)}"
        }
