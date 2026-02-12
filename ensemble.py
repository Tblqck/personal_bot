# ensemble.py
import asyncio
from core_brain import get_ensemble_intent as core_brain_intent
from task_utils import normalize_user_id, load_user_tasks
from ai_core_packet import process_packet as ai_chat_processor
from ai_core_create import process_create_packet as ai_create_processor
from ai_core_update import process_update_packet as ai_update_processor
from ai_core_delete import process_delete_packet as ai_delete_processor
from list_fun import get_user_task_list  # your GPT-based task listing

# -----------------------
# Async stub for list actions
# -----------------------
async def _get_list_tasks(user_id):
    uid = normalize_user_id(user_id)
    tasks = load_user_tasks(uid)
    await asyncio.sleep(0.05)  # simulate async
    return tasks

# -----------------------
# Main ensemble router
# -----------------------
def get_ensemble_response(packet):
    """
    Routes user action based on detected intent from core brain.
    Calls ai_core_packet only for 'chat' action.
    """
    user_id = packet.get("user_id")
    if not user_id:
        return {
            "action": "chat",
            "parameters": {},
            "ai_comment": "ENSEMBLE_CHAT_NO_USER",
            "response_text": "User ID missing."
        }

    # ----- Step 1: Detect intent via core brain -----
    intent_result = core_brain_intent(packet)
    intent = intent_result.get("intent", "chat")

    # ----- Step 2: Trigger action based on intent -----
    if intent == "create":
        create_result = ai_create_processor({**packet, "intent": "create"})
        params = create_result.get("parameters") or {}
        params.setdefault("title", None)
        params.setdefault("details", None)
        params.setdefault("due", None)

        return {
            "action": "create",
            "parameters": params,
            "ai_comment": create_result.get("ai_comment", "ENSEMBLE_CREATE"),
            "response_text": create_result.get("response_text", "Task creation suggested.")
        }

    
    elif intent == "update":
        update_result = ai_update_processor(packet)

        return {
            "action": "update",
            "parameters": update_result.get("parameters", {}),
            "ai_comment": update_result.get("ai_comment", "ENSEMBLE_UPDATE"),
            "response_text": update_result.get("response_text")
        }
    elif intent == "delete":
        delete_result = ai_delete_processor(packet)

        return {
            "action": "delete",
            "parameters": delete_result.get("parameters", {}),
            "ai_comment": delete_result.get("ai_comment", "ENSEMBLE_DELETE"),
            "response_text": delete_result.get("response_text")
        }

    

    elif intent == "list":
        import pytz
        from datetime import datetime
        from list_fun import get_user_task_list

        # 1️⃣ Get user info
        user_message = packet.get("user_message", "Show all")
        user_tz = packet.get("user_timezone", "UTC")

        # 2️⃣ Current time in user's timezone
        tz = pytz.timezone(user_tz)
        now = datetime.now(tz)

        # 3️⃣ Call GPT-powered list_fun
        results_dict = get_user_task_list(user_id, user_tz, [user_message])
        tasks = results_dict.get(user_message, {}).get("tasks", [])

        # 4️⃣ Extract just google_ids
        google_ids = [t["google_id"] for t in tasks]

        # 5️⃣ Return structured response for intent_engine
        return {
            "action": "list",
            "parameters": {"google_ids": google_ids},  # only google ids
            "ai_comment": "ENSEMBLE_LIST",
            "response_text": None  # optional: you can fill a message if needed
        }




    elif intent == "chat":
        chat_result = ai_chat_processor({**packet, "intent": "chat"})
        return {
            "action": "chat",
            "parameters": chat_result.get("parameters", {}),
            "ai_comment": chat_result.get("ai_comment", ""),
            "response_text": chat_result.get("response_text", "Okay.")
        }

    # ----- Default fallback -----
    return {
        "action": "chat",
        "parameters": {},
        "ai_comment": "ENSEMBLE_CHAT_DEFAULT",
        "response_text": "This is a default chat response."
    }


# -----------------------
# Optional test block
# -----------------------
if __name__ == "__main__":
    test_packet = {
        "user_id": "user_123",
        "user_message": "Delete my call with mom on Sunday",
        "chat_context": [],
        "tasks": [],
        "user_timezone": "Africa/Lagos",
        "current_time": "2026-02-11T12:00:00+01:00"
    }
    result = get_ensemble_response(test_packet)
    print("DEBUG ensemble result:", result)
