import os
import json
import time
from datetime import datetime
import pytz
from dotenv import load_dotenv
from openai import OpenAI
import csv

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
TASKS_CSV = "tasks.csv"

# -----------------------
# CSV / Task helpers
# -----------------------
def normalize_user_id(user_id):
    return user_id if str(user_id).startswith("user_") else f"user_{user_id}"

def load_all_tasks():
    if not os.path.exists(TASKS_CSV):
        return []
    with open(TASKS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        for r in rows:
            r.setdefault("ai_comment", "")
        return rows

def load_user_tasks(user_id):
    uid = normalize_user_id(user_id)
    all_tasks = load_all_tasks()
    return [t for t in all_tasks if t["user_id"] == uid]

# -----------------------
# GPT helpers
# -----------------------
def extract_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                return None
        return None

def gpt_filter_tasks(user_message: str, user_tz: str, current_time: datetime, tasks: list):
    """
    Ask GPT to return only tasks (title + google_id) matching user_message timeframe
    """
    tz_str = f"{user_tz} time"
    system_prompt = (
        "You are a task assistant. You are given a list of tasks with 'title', 'google_id', 'due'. "
        "Return ONLY tasks that match the user query timeframe, and ONLY include 'title' and 'google_id' in JSON. "
        "Do NOT include extra text or explanation."
    )

    tasks_json = json.dumps(tasks)
    user_prompt = f"""
Current date and time: {current_time.isoformat()} ({tz_str})
User message: "{user_message}"
User tasks: {tasks_json}
Return a JSON object like:
{{
    "tasks": [
        {{"title": "Task title", "google_id": "XYZ"}}
    ]
}}
"""

    start_time = time.time()
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=500,
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
        return {"tasks": [], "elapsed_seconds": elapsed}

    data["elapsed_seconds"] = elapsed
    return data

# -----------------------
# Public callable function
# -----------------------
def get_user_task_list(user_id: str, user_tz: str, messages: list):
    """
    Main callable function.
    user_id: str -> e.g. "user_7416057134"
    user_tz: str -> e.g. "Africa/Lagos"
    messages: list of strings (queries)
    Returns: dict -> {message: {"tasks": [...], "elapsed_seconds": float}}
    """
    now = datetime.now(pytz.timezone(user_tz))
    user_tasks = load_user_tasks(user_id)

    results = {}
    for msg in messages:
        if msg.lower() == "show all":
            filtered = [{"title": t["title"], "google_id": t["google_id"]} for t in user_tasks]
            elapsed = 0
        else:
            result = gpt_filter_tasks(msg, user_tz, now, user_tasks)
            filtered = result.get("tasks", [])
            elapsed = result.get("elapsed_seconds", 0)

        results[msg] = {"tasks": filtered, "elapsed_seconds": elapsed}

    return results
