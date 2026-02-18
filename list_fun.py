import os
import json
import time
from datetime import datetime
import pytz
from dotenv import load_dotenv
from openai import OpenAI
import csv
import re

# =====================================================
# CONFIG – choose provider here
# =====================================================

LLM_PROVIDER = "openai"      # "openai" or "openrouter"

OPENAI_MODEL = "gpt-4o-mini"
OPENROUTER_MODEL = "openai/gpt-5.2"

TASKS_CSV = "tasks.csv"

# =====================================================
# ENV
# =====================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if LLM_PROVIDER == "openai":
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not found in .env")
elif LLM_PROVIDER == "openrouter":
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in .env")
else:
    raise ValueError("LLM_PROVIDER must be 'openai' or 'openrouter'")

# =====================================================
# CLIENT
# =====================================================

if LLM_PROVIDER == "openai":
    client = OpenAI(api_key=OPENAI_API_KEY)
    MODEL = OPENAI_MODEL
else:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    MODEL = OPENROUTER_MODEL

# =====================================================
# CSV helpers
# =====================================================

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
    return [t for t in all_tasks if normalize_user_id(t.get("user_id")) == uid]

# =====================================================
# GPT helpers
# =====================================================

def extract_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group())
        except Exception:
            return None

# =====================================================
# LLM filtering
# =====================================================

def gpt_filter_tasks(user_message: str, user_tz: str, current_time: datetime, tasks: list):
    tz_str = f"{user_tz} time"

    # --------- Pre-strip status fields ----------
    tasks_for_model = [
        {k: v for k, v in t.items() if k not in ("status", "google_status")}
        for t in tasks
    ]

    system_prompt = (
        "You are a task filtering engine.\n"
        "You receive a list of tasks with 'title', 'google_id', and 'due'.\n"
        "Ignore any 'status' or 'google_status' fields.\n"
        "A task is pending if its 'due' is in the future relative to current_time.\n"
        "Return ONLY tasks that match the user's query.\n"
        "Return STRICT JSON with only 'title' and 'google_id'.\n"
        "Do not include extra text or explanation."
    )

    tasks_json = json.dumps(tasks_for_model, ensure_ascii=False)

    user_prompt = f"""
Current date and time: {current_time.isoformat()} ({tz_str})

User message:
"{user_message}"

User tasks:
{tasks_json}

Return exactly:
{{
  "tasks": [
    {{"title": "...", "google_id": "..."}}
  ]
}}
"""

    start = time.time()

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=500
    )

    elapsed = time.time() - start
    text = completion.choices[0].message.content or ""
    data = extract_json(text)
    if not data or "tasks" not in data:
        return {"tasks": [], "elapsed_seconds": elapsed}

    data["elapsed_seconds"] = elapsed
    return data

# =====================================================
# PUBLIC API
# =====================================================

def get_user_task_list(user_id: str, user_tz: str, messages: list):
    now = datetime.now(pytz.timezone(user_tz))
    all_user_tasks = load_user_tasks(user_id)

    results = {}

    for msg in messages:
        msg_l = msg.lower()

        # ----------------- HARD FILTER -----------------
        # Remove these hard filters, AI will decide
        filtered_tasks = all_user_tasks

        # ----------------- SHOW ALL -----------------
        if msg_l.strip() == "show all":
            final = [
                {"title": t.get("title"), "google_id": t.get("google_id")}
                for t in filtered_tasks
            ]
            elapsed = 0

        else:
            r = gpt_filter_tasks(msg, user_tz, now, filtered_tasks)
            final = r.get("tasks", [])
            elapsed = r.get("elapsed_seconds", 0)

        results[msg] = {"tasks": final, "elapsed_seconds": elapsed}

    return results
