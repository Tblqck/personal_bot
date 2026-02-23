
# Personal Tasks Bot

**Personal Tasks Bot** is a Telegram bot that allows users to manage their Google Tasks directly from Telegram. It also integrates with Google Calendar to track task times accurately.  

This project is a personal project and is **not affiliated with any company**.  

---

## Features

- **Google Tasks Management:** Create, update, and delete tasks directly from Telegram.
- **Task Fetching:** Fetch all tasks from Google Tasks.
- **Calendar Integration:** For tasks with only a date, the bot uses Google Calendar to find the exact time.
- **CSV Storage:** Tasks are stored locally in a CSV (`tasks.csv`) for internal bot processing.
- **Multi-user Support:** Each user authorizes the bot individually via Google OAuth.

---

## Data and Privacy

- The bot only accesses the following Google data:
  - **Google Tasks:** Read, create, update, and delete tasks.
  - **Google Calendar:** Read events to determine exact task times (only when needed).  
- Each user’s **refresh token** is stored securely in a local JSON database (`database.json`) to enable continuous access without requiring repeated logins.
- No user data is shared with third parties.
- All task data remains local to the bot.


## Requirements

- Python 3.11+
- Packages: `requests`, `pytz`

Install dependencies using:

```bash
pip install -r requirements.txt
````

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Tblqck/personal_bot.git
cd personal_bot
```

2. Configure your Google OAuth credentials in `config.py`:

```python
GOOGLE_CLIENT_ID = "<YOUR_CLIENT_ID>"
GOOGLE_CLIENT_SECRET = "<YOUR_CLIENT_SECRET>"
REDIRECT_URI = "<YOUR_REDIRECT_URI>"
SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar"
]
DATABASE_FILE = "database.json"
```

3. Run the bot and authorize with your Google account. The bot will generate a **refresh token** and store it locally.

---

## How OAuth Works

1. Each user logs in via Google OAuth.
2. The bot receives a **refresh token** and stores it locally.
3. The refresh token allows the bot to access Tasks and Calendar data without the user needing to log in again.
4. Users can revoke access at any time via their Google account settings.

> **Note:** If the app is in testing mode (unverified), only test users added in the Google Cloud console can log in. Public users will require app verification.

---

## Usage

* The bot automatically synchronizes tasks from Google Tasks and Calendar.
* Tasks created via Telegram are stored locally and synced back to Google Tasks.
* Tasks created directly in Google Tasks are fetched, and the bot tries to resolve the exact time using Calendar if only a date is provided.

---

## Disclaimer

* This is a **personal project**. Use at your own risk.
* Google OAuth verification is required for public usage.
* All user data is handled responsibly and only used for the bot’s intended functionality.

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.

---

## Repository

GitHub: [https://github.com/Tblqck/personal_bot](https://github.com/Tblqck/personal_bot)

```


