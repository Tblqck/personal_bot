import os
import json
import re
import time
from datetime import datetime
import pytz
from dotenv import load_dotenv
from openai import OpenAI

# -----------------------
# Config
# -----------------------
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

MODEL = "openai/gpt-5.2"

# -----------------------
# GPT helpers
# -----------------------
def extract_json(text: str):
    """
    Extract JSON object from GPT response robustly
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # fallback: extract first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                return None
        return None

def decode_timeframe(user_message: str, user_tz: str, current_time: datetime):
    """
    Only extract absolute times (explicit date/time references).
    If no explicit time mentioned, return None.
    """
    tz_str = f"{user_tz} time"
    system_prompt = (
        "You are a time-parsing assistant. "
        "Return ONLY a JSON object with 'start_time' and 'end_time' in ISO format. "
        "Convert relative times like 'tomorrow 10 am', 'Sunday 11 am' into absolute ISO datetimes "
        f"using the current date and time: {current_time.isoformat()} ({tz_str}). "
        "If no explicit date/time is mentioned, return null for both start_time and end_time. "
        "Do NOT include tasks, ranges like 'today', 'this week', or any extra text."
    )

    user_prompt = f"""
User message: "{user_message}"
Return a JSON object like:
{{
  "start_time": "YYYY-MM-DDTHH:MM:SS",
  "end_time": "YYYY-MM-DDTHH:MM:SS"
}}
"""

    start_time = time.time()
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=150,
        extra_headers={
            "HTTP-Referer": "https://your-site.com",
            "X-Title": "PersonalBot"
        }
    )
    end_time = time.time()
    elapsed = end_time - start_time

    text = completion.choices[0].message.content
    data = extract_json(text)

    if not data:
        return {"start_time": None, "end_time": None, "elapsed_seconds": elapsed}

    # ensure start_time/end_time keys exist
    if "start_time" not in data:
        data["start_time"] = None
    if "end_time" not in data:
        data["end_time"] = None

    data["elapsed_seconds"] = elapsed
    return data

# -----------------------
# Test section
# -----------------------
if __name__ == "__main__":
    USER_TZ = "Africa/Lagos"
    now = datetime.now(pytz.timezone(USER_TZ))

    test_messages = [
        "next two tasks",                 # no explicit time → None
        "what do I have lined up for the month",  # no explicit time → None
        "set up a call for tomorrow by 10 am",   # explicit → should return ISO
        "tasks for tomorrow evening",     # vague → None
        "show tasks for this week",       # vague → None
        "get tasks for today",            # vague → None
        "what's next todo after that",    # vague → None
        "find me by Sunday 11 am",        # explicit → should return ISO
        "just random message with no time" # None
    ]

    for msg in test_messages:
        result = decode_timeframe(msg, USER_TZ, current_time=now)
        print(f"Message: {msg}")
        print("Start:", result.get("start_time"))
        print("End:", result.get("end_time"))
        print(f"Response time: {result.get('elapsed_seconds'):.2f} seconds")
        print("-"*50)
