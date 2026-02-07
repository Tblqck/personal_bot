# ayth_script.py
import requests
import json
from urllib.parse import urlencode, urlparse, parse_qs
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, REDIRECT_URI, SCOPES, DATABASE_FILE
import pytz
from datetime import datetime
from zoneinfo import ZoneInfo
# ----------------------
# User registration + timezone
# ----------------------


def register_user_timezone_first(user_key, tz_text):
    """
    Save user's timezone.
    tz_text comes from Telegram message.
    """

    # normalize
    tz_text = tz_text.strip()

    # validate timezone
    try:
        ZoneInfo(tz_text)
    except Exception:
        raise ValueError("Invalid timezone")

    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
    except FileNotFoundError:
        db = {}

    if user_key not in db:
        db[user_key] = {}

    db[user_key]["timezone"] = tz_text

    with open(DATABASE_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)

    return tz_text

# ----------------------
# Google OAuth
# ----------------------
def generate_auth_url():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent"
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

def register_user_via_url(user_key, full_url):
    parsed = urlparse(full_url)
    query_params = parse_qs(parsed.query)
    code_list = query_params.get("code")
    if not code_list:
        raise ValueError("No code parameter found in URL.")
    code = code_list[0]

    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    resp = requests.post("https://oauth2.googleapis.com/token", data=data)
    tokens = resp.json()

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise Exception("No refresh token received.")

    try:
        with open(DATABASE_FILE) as f:
            db = json.load(f)
    except FileNotFoundError:
        db = {}

    if user_key not in db:
        db[user_key] = {}

    db[user_key]["refresh_token"] = refresh_token

    with open(DATABASE_FILE, "w") as f:
        json.dump(db, f, indent=2)

    print(f"✅ User '{user_key}' registered with Google account")
    return tokens

def _get_access_token(user_key):
    with open(DATABASE_FILE) as f:
        db = json.load(f)
    refresh_token = db[user_key]["refresh_token"]
    data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    resp = requests.post("https://oauth2.googleapis.com/token", data=data)
    return resp.json()["access_token"]

# ----------------------
# Task operations
# ----------------------
def create_task(title, due, user_key, details=None):
    access_token = _get_access_token(user_key)
    headers = {"Authorization": f"Bearer {access_token}"}
    task_data = {"title": title, "due": due}
    if details:
        task_data["notes"] = details
    resp = requests.post(
        "https://tasks.googleapis.com/tasks/v1/lists/@default/tasks",
        headers=headers,
        json=task_data
    )
    return resp.json()

def list_tasks(user_key):
    access_token = _get_access_token(user_key)
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(
        "https://tasks.googleapis.com/tasks/v1/lists/@default/tasks",
        headers=headers
    )
    return resp.json().get("items", [])

def update_task(task_id, user_key, title=None, details=None, due=None):
    access_token = _get_access_token(user_key)
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {}
    if title: payload["title"] = title
    if details: payload["notes"] = details
    if due: payload["due"] = due
    resp = requests.patch(
        f"https://tasks.googleapis.com/tasks/v1/lists/@default/tasks/{task_id}",
        headers=headers,
        json=payload
    )
    return resp.json()

def delete_task(task_id, user_key):
    access_token = _get_access_token(user_key)
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.delete(
        f"https://tasks.googleapis.com/tasks/v1/lists/@default/tasks/{task_id}",
        headers=headers
    )
    return resp.status_code == 204

def complete_task(task_id, user_key):
    """
    Marks a Google Task as done using the official API.
    This does NOT call update_task() and avoids 'status' keyword errors.
    """
    access_token = _get_access_token(user_key)
    headers = {"Authorization": f"Bearer {access_token}"}

    now_iso = datetime.utcnow().isoformat() + "Z"
    task_body = {"status": "completed", "completed": now_iso}

    resp = requests.patch(
        f"https://tasks.googleapis.com/tasks/v1/lists/@default/tasks/{task_id}",
        headers=headers,
        json=task_body
    )
    return resp.json()

def mark_task_done(task_id, user_key):
    """
    Alias for complete_task.
    """
    return complete_task(task_id, user_key)
