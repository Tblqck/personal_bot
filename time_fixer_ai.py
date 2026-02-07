# time_fixer_ai.py

import os
import json
import openai
from datetime import datetime
import pytz
from dotenv import load_dotenv

# -------------------------------
# Load API key from environment
# -------------------------------
load_dotenv()  # ensure .env is loaded
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not set in environment or .env")

openai.api_key = OPENAI_API_KEY

# -------------------------------
# AI-based time fixer
# -------------------------------
def fix_time_with_model(time_text: str, user_timezone: str = "UTC") -> str | None:
    """
    Uses OpenAI LLM to convert human time expressions into ISO 8601 datetime.

    Args:
        time_text: e.g., "tomorrow morning by 10 am", "a week before 3rd April"
        user_timezone: IANA timezone string, e.g., "Africa/Lagos"

    Returns:
        ISO 8601 string with timezone, e.g., "2026-02-06T17:00:00+01:00"
        or None if parsing fails
    """

    # Reference time for relative expressions
    try:
        now = datetime.now(pytz.timezone(user_timezone)).isoformat()
    except Exception:
        now = datetime.utcnow().isoformat()

    prompt = f"""
You are a datetime normalization engine.

Convert this human-readable time expression into ISO 8601 datetime string.
Use the reference current time: {now}
Assume timezone: {user_timezone}

Text to convert:
"{time_text}"

Rules:
- Return STRICT JSON
- Key: "iso"
- If unable to infer, return null
- Do NOT add explanations or extra text

Format example:
{{"iso": "2026-02-06T17:00:00+01:00"}}
"""

    try:
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a datetime normalization engine."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        content = resp.choices[0].message.content.strip()
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == -1 or start >= end:
            return None

        data = json.loads(content[start:end])
        iso = data.get("iso")
        return iso

    except Exception as e:
        print(f"⚠️ AI time fixer failed for '{time_text}': {e}")
        return None


# -------------------------------
# Self-test
# -------------------------------
if __name__ == "__main__":
    tests = [
        "tomorrow morning by 10 am",
        "a week before the 3rd of April",
        "next Friday at 5pm",
        "2 days after 5th Feb"
    ]

    for t in tests:
        print(f"Input: {t}")
        iso = fix_time_with_model(t, "Africa/Lagos")
        print(f"Output: {iso}\n")
