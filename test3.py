import os
from datetime import datetime
import pytz

from core_brain import get_ensemble_intent
from task_utils import (
    load_user_tasks,
    get_user_timezone,
    normalize_user_id
)

# -------------------------------------------------
# This mimics your ai_thought() packet builder
# but calls core_brain instead of ensemble.py
# -------------------------------------------------

def ai_thought_core_brain(user_id, message):

    tasks = load_user_tasks(user_id)[:40]

    user_tz = get_user_timezone(user_id)
    now = datetime.now(pytz.timezone(user_tz))

    packet = {
        "user_id": normalize_user_id(user_id),
        "user_message": message,
        "chat_context": [],   # keep empty for this test
        "tasks": tasks,
        "user_timezone": user_tz,
        "current_time": now.isoformat()
    }

    result = get_ensemble_intent(packet)

    return packet, result


# -------------------------------------------------
# Test runner
# -------------------------------------------------

if __name__ == "__main__":

    user_id = "user_1249752083"
    message = "what task i have pending"

    packet, result = ai_thought_core_brain(user_id, message)

    print("\n================ PACKET SENT TO core_brain ================\n")
    from pprint import pprint
    pprint(packet)

    print("\n================ FINAL RESULT =============================\n")
    pprint({
        "intent": result.get("intent"),
        "response": result.get("response"),
        "votes": result.get("stats", {}).get("votes")
    })

    print("\n================ PER MODEL ================================\n")

    for r in result["stats"]["model_results"]:
        print("-------------------------------------")
        print("MODEL     :", r.get("model"))
        print("INTENT    :", r.get("intent"))
        print("CONFIDENCE:", r.get("confidence"))
        print("MESSAGE   :", r.get("message"))
