# ai_core_delete.py

import os
import json
from dotenv import load_dotenv
import openai

from task_utils import load_all_tasks, normalize_user_id

# -----------------------
# Load OpenAI API Key
# -----------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not set in .env!")

openai.api_key = OPENAI_API_KEY

# -----------------------
# Helpers
# -----------------------

def _load_user_tasks_up_to_70(user_id):
    uid = normalize_user_id(user_id)
    all_rows = load_all_tasks()
    user_tasks = [r for r in all_rows if r.get("user_id") == uid]
    return user_tasks[:70]  # cap at 70

def _reduce_context(chat_context, limit=6):
    if not chat_context:
        return []
    return chat_context[-limit:]

def _format_recent_messages(rows):
    if not rows:
        return "No recent messages."
    lines = []
    for m in rows:
        role = m.get("role", "user")
        content = m.get("content") or m.get("message") or ""
        lines.append(f"{role}: {content}")
    return "\n".join(lines)

def _format_tasks(tasks):
    if not tasks:
        return "No tasks."
    lines = []
    for t in tasks:
        lines.append(
            json.dumps(
                {
                    "google_id": t.get("google_id"),
                    "title": t.get("title"),
                    "details": t.get("details"),
                    "due": t.get("due"),
                    "status": t.get("status")
                },
                ensure_ascii=False
            )
        )
    return "\n".join(lines)

# -----------------------
# Prompt
# -----------------------

SYSTEM_PROMPT_TEMPLATE = """
You are a specialized AI reminder assistant for deleting a task.

You MUST return STRICT JSON in the following format:

{{
  "action": "delete",
  "parameters": {{
    "google_id": string
  }},
  "ai_comment": short advice to the user about this deletion
}}

Rules:
- You are deleting an existing task, not creating or updating.
- You will be given a list of the user's existing tasks.
- Select exactly ONE task to delete.
- The google_id MUST match one of the provided tasks.
- Only output JSON. No markdown, no explanations.
- You are acting as the user's reminder assistant.

User request:
{user_message}

Current time:
{current_time}

User timezone:
{user_timezone}

Recent conversation (max 6 messages):
{recent_messages}

User tasks (max 70 tasks):
{user_tasks}
"""

# -----------------------
# Main API
# -----------------------

def process_delete_packet(packet):
    """
    packet:
    {
        user_id,
        user_message,
        chat_context,
        tasks,   # ignored, we reload properly
        user_timezone,
        current_time
    }
    """

    user_id = packet.get("user_id")
    user_message = (packet.get("user_message") or "").strip()
    user_timezone = packet.get("user_timezone", "UTC")
    current_time = packet.get("current_time")

    if not user_id:
        return _empty_delete("Missing user id.")

    if not user_message:
        return _empty_delete("No delete request provided.")

    # -----------------------
    # Prepare context & tasks
    # -----------------------

    reduced_context = _reduce_context(packet.get("chat_context", []), 6)
    user_tasks = _load_user_tasks_up_to_70(user_id)

    recent_messages_text = _format_recent_messages(reduced_context)
    user_tasks_text = _format_tasks(user_tasks)

    # -----------------------
    # Build prompt
    # -----------------------

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        user_message=user_message,
        current_time=current_time,
        user_timezone=user_timezone,
        recent_messages=recent_messages_text,
        user_tasks=user_tasks_text
    )

    messages = [{"role": "system", "content": system_prompt}]

    # -----------------------
    # OpenAI call
    # -----------------------

    try:
        resp = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.2
        )

        raw = resp.choices[0].message.content.strip()

        start = raw.find("{")
        end = raw.rfind("}") + 1

        if start == -1 or end <= start:
            return _empty_delete("Invalid delete response from AI.")

        json_text = raw[start:end]

        try:
            result = json.loads(json_text)
        except Exception:
            return _empty_delete("Could not parse delete instruction.")

    except Exception as e:
        return _empty_delete(f"Delete model error: {str(e)}")

    # -----------------------
    # Normalize result
    # -----------------------

    result.setdefault("action", "delete")
    result.setdefault("parameters", {"google_id": None})
    result.setdefault("ai_comment", "")
    result.setdefault("response_text", "Task deleted.")

    # -----------------------
    # Safety check: ensure google_id belongs to user tasks
    # -----------------------

    allowed_ids = {t.get("google_id") for t in user_tasks if t.get("google_id")}

    if result["parameters"].get("google_id") not in allowed_ids:
        return _empty_delete(
            "Could not confidently identify which task to delete."
        )

    return result

# -----------------------
# Fallback
# -----------------------

def _empty_delete(reason):
    return {
        "action": "delete",
        "parameters": {"google_id": None},
        "ai_comment": reason,
        "response_text": "I couldn't determine which task to delete. Please be more specific."
    }
