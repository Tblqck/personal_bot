import json

# Path to your downloaded JSON
CREDENTIALS_FILE = "safe_keep/client.json"

with open(CREDENTIALS_FILE) as f:
    creds = json.load(f)

# "web" key instead of "installed"
GOOGLE_CLIENT_ID = creds["web"]["client_id"]
GOOGLE_CLIENT_SECRET = creds["web"]["client_secret"]
REDIRECT_URI = creds["web"]["redirect_uris"][0]  # usually the first URI

SCOPES = ["https://www.googleapis.com/auth/tasks"]

TELEGRAM_BOT_TOKEN = "7445887782:AAED2ofAYnSkHvAuYcTSQy9GcMOJ4eVFhOY"
DATABASE_FILE = "database.json"
