# ai_core_packet.py
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
# GPT System Prompt Template
# -----------------------
SYSTEM_PROMPT_TEMPLATE = """
You are a specialized AI for processing user intents in a task management system.
You ONLY analyze the user's message, their detected intent, and any relevant context.
You MUST return STRICT JSON with keys:

- action: create, update, delete, list, chat
- parameters: dict with relevant fields (title, details, due, list_scope)
- ai_comment: short helpful hints or clarifications
- response_text: user-facing short reply

Rules:
- Respect the provided intent. Do not invent anything.
- Dates/times must be ISO8601 format if present.
- If title/due/details are missing or unclear, use null.
- Do not include explanations, internal notes, or markdown.
- Only output JSON.

User intent: {intent}
"""

# -----------------------
# Main AI Callable
# -----------------------
def process_packet(packet):
    """
    Routes user action based on detected intent from core brain.

    Args:
        packet (dict): {
            "user_id": str,
            "user_message": str,
            "chat_context": list of dicts [{"role":..., "message"/"content":..., "timestamp":...}, ...],
            "tasks": list of dicts,
            "user_timezone": str,
            "current_time": ISO string,
            "intent": str (optional)
        }

    Returns:
        dict: {
            "action": create|update|delete|list|chat,
            "parameters": dict(title, details, due, list_scope),
            "ai_comment": str,
            "response_text": str
        }
    """
    user_message = packet.get("user_message", "")
    intent = packet.get("intent", "chat")
    user_id = packet.get("user_id")
    user_timezone = packet.get("user_timezone", "UTC")
    chat_context = packet.get("chat_context", [])

    # -----------------------
    # Normalize context for OpenAI
    # -----------------------
    formatted_context = []
    for msg in chat_context:
        role = msg.get("role", "user")
        # support both 'message' and 'content' keys
        content = msg.get("content") or msg.get("message") or ""
        formatted_context.append({"role": role, "content": str(content)})

    # Add current message as last item
    formatted_context.append({"role": "user", "content": str(user_message)})

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(intent=intent)
    messages = [{"role": "system", "content": system_prompt}] + formatted_context

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

        # Robust JSON extraction
        start = content.find("{")
        end = content.rfind("}") + 1
        json_text = content[start:end]

        try:
            result = json.loads(json_text)
        except Exception:
            result = {
                "action": "chat",
                "parameters": {"title": None, "details": None, "due": None, "list_scope": None},
                "ai_comment": "",
                "response_text": content or "Sorry, I didn't understand that."
            }

    except Exception as e:
        result = {
            "action": "chat",
            "parameters": {"title": None, "details": None, "due": None, "list_scope": None},
            "ai_comment": "",
            "response_text": f"Sorry, I couldn't process that: {str(e)}"
        }

    # -----------------------
    # Ensure all keys exist
    # -----------------------
    result.setdefault("action", "chat")
    result.setdefault("parameters", {"title": None, "details": None, "due": None, "list_scope": None})
    result.setdefault("ai_comment", "")
    result.setdefault("response_text", "Okay.")

    # -----------------------
    # Fix due date if exists
    # -----------------------
    due = result["parameters"].get("due")
    if due and user_id:
        try:
            fixed = fix_time_from_text(due, user_timezone=user_timezone)
            if fixed:
                result["parameters"]["due"] = fixed
        except Exception:
            pass

    return result
