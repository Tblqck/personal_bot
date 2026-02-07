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
import hard_starter


# -------------------------------------------------
# Internal guard: ensure reminder engine starts ONCE
# -------------------------------------------------
_engine_started = False


def _ensure_reminder_engine():
    global _engine_started

    if _engine_started:
        return

    try:
        hard_starter.ensure_engine_running()
    except Exception as e:
        print("⚠️ Reminder engine start failed:", e)

    _engine_started = True


# -------------------------------------------------
# In-memory states
# -------------------------------------------------
conversation_state = {}      # user_id -> frame state
onboarding_pending = {}     # google oauth
timezone_pending = {}       # user_id -> True


# -------------------------------------------------
# Main entry point
# -------------------------------------------------
def handle_user_message(user_id, message_text):

    _ensure_reminder_engine()

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
    if user_id in timezone_pending:

        tz_text = message_text.strip()

        try:
            tz = register_user_timezone_first(user_key, tz_text)
        except TypeError:
            # fallback if your function only expects one arg
            tz = register_user_timezone_first(user_key, tz_text)

        timezone_pending.pop(user_id, None)

        return {
            "status": "ok",
            "message": (
                f" Timezone set to **{tz}**.\n\n"
                "Now connect your Google Tasks account using /connect."
            )
        }

    if user_key not in db or "timezone" not in db.get(user_key, {}):

        timezone_pending[user_id] = True

        return {
            "status": "awaiting",
            "next_slot": "timezone",
            "message": (
                " Please enter your timezone.\n\n"
                "Example:\n"
                "Africa/Lagos"
            )
        }

    # -------------------------------------------------
    # Step 1: /connect onboarding
    # -------------------------------------------------
    if message_text.strip().lower() == "/connect":
        auth_url = generate_auth_url()
        onboarding_pending[user_id] = True

        
        return {
            "status": "ok",
            "message": (
                " Connect your Google Tasks account (one-time setup)\n\n"
                " Open this link in your browser:\n"
                f"{auth_url}\n\n"

                "> Important: Google has NOT yet verified this app.\n"
                "You will see a warning page. This is normal.\n\n"

                "> Please follow these exact steps:\n\n"

                "1️ On the warning page, click:\n"
                "   ➜ Advanced\n\n"

                "2️ Then click:\n"
                "   ➜ Go to Telegram Tasks Bot (unsafe)\n\n"

                "3️ You will be taken to a Google sign-in page.\n"
                "   Sign in to your Google account.\n\n"

                "4️ Google will show another warning page.\n"
                "   Click:\n"
                "   ➜ Continue\n\n"

                "5️ After that, your browser will open a page that looks broken and says:\n"
                "   “This site can’t be reached – localhost refused to connect”.\n\n"

                " This is expected.\n\n"

                "6️ Copy the FULL URL from your browser address bar\n"
                "   (the localhost page URL),\n"
                "   and paste that entire link here in Telegram.\n\n"

                "> I will use that link to finish connecting your Google account."
            ),
        }

    # -------------------------------------------------
    # Step 2: OAuth redirect URL handling
    # -------------------------------------------------
    if onboarding_pending.get(user_id):

        try:
            register_user_via_url(
                user_key=user_key,
                full_url=message_text.strip()
            )

            onboarding_pending.pop(user_id, None)

            return {
                "status": "ok",
                "message": "✅ Google Tasks account connected successfully!"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"❌ Failed to complete setup: {str(e)}"
            }

    # -------------------------------------------------
    # Step 3: Slot filling
    # -------------------------------------------------
    if user_id in conversation_state:

        state = conversation_state[user_id]
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

                conversation_state.pop(user_id, None)

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

            conversation_state.pop(user_id, None)

            return {
                "status": "ok",
                "message": f"✅ Task **{frame['title']}** scheduled."
            }

        except Exception as e:
            conversation_state.pop(user_id, None)

            return {
                "status": "error",
                "message": f"❌ Failed to save task: {str(e)}"
            }

    # -------------------------------------------------
    # Step 4: AI intent parsing
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
