# Privacy Policy – Personal Tasks Bot

**Effective Date:** February 2026

## 1. Introduction

Personal Tasks Bot is a Telegram bot designed to help users manage their Google Tasks and Calendar events directly from Telegram. This document explains how the bot handles your data and what permissions it requires.

---

## 2. Data Collected

The bot only accesses data necessary for its operation:

- **Google Tasks:** Read, create, update, and delete tasks.
- **Google Calendar:** Read events to determine exact times for tasks that only have a date.
- **User Timezone:** Stored locally to correctly handle task scheduling.

All user data is stored locally in `database.json` and `tasks.csv`.

---

## 3. How Data is Used

- Tasks created in Telegram are synced to Google Tasks.
- Tasks created in Google Tasks are fetched and synced locally.
- Calendar events are used only to determine the exact time for tasks that have a date but no time.

No data is shared with third parties or used for advertising.

---

## 4. Google OAuth Access

- The bot requests the following OAuth scopes:
  - `https://www.googleapis.com/auth/tasks` – Full access to manage your tasks.
  - `https://www.googleapis.com/auth/calendar` – Read access to calendar events to resolve task times.

- The bot stores a **refresh token** to maintain access without requiring repeated logins. Users can revoke this token anytime from their Google Account.

---

## 5. User Control

- Users can remove the bot's access at any time via [Google Account Permissions](https://myaccount.google.com/permissions).
- All tasks and data handled by the bot remain local unless synced to Google Tasks or Calendar.

---

## 6. Security

- All sensitive data (refresh tokens, timezone, task data) is stored locally in files (`database.json`, `tasks.csv`).
- The bot does not transmit sensitive data outside of Google APIs.

---

## 7. Contact

For any privacy-related questions, issues, or concerns:

- GitHub: [https://github.com/Tblqck/personal_bot](https://github.com/Tblqck/personal_bot)
- Author: Abasiekeme Hanson

---

**By using Personal Tasks Bot, you consent to the collection and use of your data as described in this Privacy Policy.**
