# ai_core_create.py
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import openai
from time_fixer import fix_time_from_text

# -----------------------
# Load OpenAI API Key
# -----------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not set in .env!")
openai.api_key = OPENAI_API_KEY

# -----------------------
# GPT System Prompt Template for Task Creation
# -----------------------
SYSTEM_PROMPT_TEMPLATE = """
You are a specialized AI for creating tasks from a user's message.
You MUST return STRICT JSON with keys:

- action: "create"
- parameters: dict with:
    - title: short task name
    - details: task description/summary
    - due: ISO8601 datetime string
- ai_comment: short advice or tip about the task
- response_text: user-facing confirmation

Rules:
- Always respect the user's intent to create a task.
- Generate a clear, concise title from the message.
- Generate a meaningful summary/details.
- Extract due date/time accurately and convert to ISO8601 respecting user's timezone.
- Provide a helpful, actionable comment about the task for the user.
- If any field cannot be inferred, use null.
- Only output JSON, no explanations or markdown.

User message: {user_message}
Current time: {current_time} (ISO string)
User timezone: {user_timezone}
"""

# -----------------------
# Main AI Callable
# -----------------------
def process_create_packet(packet):
    """
    Processes task creation from a user message.
    Returns JSON with title, details, due, ai_comment (advice), and response_text.
    """
    user_message = str(packet.get("user_message", "")).strip()
    user_id = packet.get("user_id")
    user_timezone = packet.get("user_timezone", "UTC")
    current_time = packet.get("current_time")  # ISO string

    if not user_message:
        return {
            "action": "create",
            "parameters": {"title": None, "details": None, "due": None},
            "ai_comment": "No message provided",
            "response_text": "Cannot create task: message is empty."
        }

    # -----------------------
    # Build system prompt
    # -----------------------
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        user_message=user_message,
        current_time=current_time,
        user_timezone=user_timezone
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    # -----------------------
    # Call OpenAI GPT
    # -----------------------
    try:
        resp = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.2
        )

        content = resp.choices[0].message.content.strip()
        # Extract JSON robustly
        start = content.find("{")
        end = content.rfind("}") + 1
        json_text = content[start:end]

        try:
            result = json.loads(json_text)
        except Exception:
            # Fallback: minimal creation
            due_time = fix_time_from_text(user_message, user_timezone, current_time)
            result = {
                "action": "create",
                "parameters": {
                    "title": user_message[:50],
                    "details": user_message,
                    "due": due_time
                },
                "ai_comment": f"Remember to complete this task on time.",
                "response_text": f"Created task: '{user_message[:50]}'"
            }

    except Exception as e:
        due_time = fix_time_from_text(user_message, user_timezone, current_time)
        result = {
            "action": "create",
            "parameters": {
                "title": user_message[:50],
                "details": user_message,
                "due": due_time
            },
            "ai_comment": f"Created task with best effort. Remember to follow up on it.",
            "response_text": f"Created task with best effort due to API error: {str(e)}"
        }

    # -----------------------
    # Ensure keys exist
    # -----------------------
    result.setdefault("action", "create")
    result.setdefault("parameters", {"title": None, "details": None, "due": None})
    result.setdefault("ai_comment", "Consider completing this task promptly.")
    result.setdefault("response_text", f"Created task: '{user_message[:50]}'")

    # -----------------------
    # Fix due date
    # -----------------------
    due = result["parameters"].get("due")
    if due and user_id:
        try:
            fixed = fix_time_from_text(due, user_timezone=user_timezone, reference_time=current_time)
            if fixed:
                result["parameters"]["due"] = fixed
        except Exception:
            pass

    return result
