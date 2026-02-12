# ai_core_update.py

import os
import json
from dotenv import load_dotenv
import openai
from time_fixer import fix_time_from_text
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
    # cap at 70 tasks
    return user_tasks[:70]

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
        lines.append(json.dumps({
            "google_id": t.get("google_id"),
            "title": t.get("title"),
            "details": t.get("details"),
            "due": t.get("due"),
            "status": t.get("status")
        }, ensure_ascii=False))
    return "\n".join(lines)

# -----------------------
# Prompt Template
# -----------------------
SYSTEM_PROMPT_TEMPLATE = """
You are a specialized AI for updating an existing task. You MUST return STRICT JSON in the following format:
{{
  "action": "update",
  "parameters": {{
    "google_id": string,
    "title": string or null,
    "details": string or null,
    "due": ISO8601 datetime string or null
  }},
  "ai_comment": short advice to the user about the update
}}

Rules:
- You are updating an existing task, not creating a new one.
- You will be given a list of the user's existing tasks.
- Select exactly ONE task to update.
- The google_id MUST match one of the provided tasks.
- Only change the fields the user actually wants to modify.
- If a field should not change, return null for that field.
- The ai_comment must be a short helpful advice about the task itself (not about formatting, parsing or the system).
- Only output JSON. No markdown, no explanations.

User request: {user_message}
Current time: {current_time}
User timezone: {user_timezone}
Recent conversation (max 6 messages): {recent_messages}
User tasks (max 70 tasks): {user_tasks}
"""

# -----------------------
# Main API
# -----------------------
def process_update_packet(packet):
    """
    packet: {
        user_id: str,
        user_message: str,
        chat_context: list[dict],
        user_timezone: str,
        current_time: ISO string
    }
    """
    user_id = packet.get("user_id")
    user_message = (packet.get("user_message") or "").strip()
    user_timezone = packet.get("user_timezone", "UTC")
    current_time = packet.get("current_time")

    if not user_id:
        return _empty_update("Missing user id.")
    if not user_message:
        return _empty_update("No update request provided.")

    # -----------------------
    # Rebuild context and tasks
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
    # OpenAI API call
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
            return _empty_update("Invalid update response from AI.")

        json_text = raw[start:end]
        try:
            result = json.loads(json_text)
        except Exception:
            return _empty_update("Could not parse update instruction.")

    except Exception as e:
        return _empty_update(f"Update model error: {str(e)}")

    # -----------------------
    # Normalize result
    # -----------------------
    result.setdefault("action", "update")
    result.setdefault("parameters", {
        "google_id": None,
        "title": None,
        "details": None,
        "due": None
    })
    result.setdefault("ai_comment", "")
    result.setdefault("response_text", "Task updated.")

    # -----------------------
    # Fix 'due' using utility
    # -----------------------
    due = result["parameters"].get("due")
    if due:
        try:
            fixed = fix_time_from_text(
                due,
                user_timezone=user_timezone,
                reference_time=current_time
            )
            if fixed:
                result["parameters"]["due"] = fixed
        except Exception:
            pass

    # -----------------------
    # Safety check: ensure google_id exists
    # -----------------------
    allowed_ids = {t.get("google_id") for t in user_tasks if t.get("google_id")}
    if result["parameters"].get("google_id") not in allowed_ids:
        return _empty_update("Could not confidently identify which task to update.")

    return result

# -----------------------
# Fallback
# -----------------------
def _empty_update(reason):
    return {
        "action": "update",
        "parameters": {
            "google_id": None,
            "title": None,
            "details": None,
            "due": None
        },
        "ai_comment": reason,
        "response_text": "I couldn't determine which task to update. Please be more specific."
    }
