import os
import csv
import json
import asyncio
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from muster_point import handle_user_message
from hard_starter import run_reminder_ai
from sync_google_tasks_to_csv import sync_user_tasks_to_csv
from config import DATABASE_FILE


# -------------------------------------------------
# env
# -------------------------------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN2")
if not BOT_TOKEN:
    raise ValueError("🚨 BOT_TOKEN2 is not set!")

REMINDERS_LOG_CSV = "reminders_sent.csv"


# -------------------------------------------------
# Telegram handlers
# -------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I’m your personal assistant bot.\n\n"
        "To connect your Google Tasks account, send /connect\n"
        "After connecting, you can send tasks in natural language."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    user_id = msg.from_user.id
    text = msg.text or msg.caption or ""

    response_dict = handle_user_message(user_id=user_id, message_text=text)
    reply = response_dict.get("message", "🤖 Something went wrong.")
    await msg.reply_text(reply)


# -------------------------------------------------
# Sender loop (CSV is the drop-box)
# -------------------------------------------------
async def send_reminders_loop(app):
    """Read reminders_sent.csv, send each row once, then delete it."""
    while True:
        try:
            if not os.path.exists(REMINDERS_LOG_CSV):
                await asyncio.sleep(60)
                continue

            with open(REMINDERS_LOG_CSV, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

            if not rows:
                await asyncio.sleep(60)
                continue

            remaining_rows = []

            for reminder in rows:
                user_id = reminder.get("user_id")
                message = reminder.get("ai_message")

                if not user_id or not message:
                    continue

                if isinstance(user_id, str) and user_id.startswith("user_"):
                    user_id = user_id.replace("user_", "")

                try:
                    await app.bot.send_message(
                        chat_id=int(user_id),
                        text=message
                    )

                    print(f"✅ Sent reminder to {user_id}")

                except Exception as e:
                    print(f"❌ Failed to send reminder to {user_id}: {e}")

                    reminder["user_id"] = user_id
                    remaining_rows.append(reminder)

            fieldnames = [
                "timestamp_utc",
                "user_id",
                "task_title",
                "minutes_left",
                "ai_message",
                "sent"
            ]

            with open(REMINDERS_LOG_CSV, "w", newline="", encoding="utf-8", encoding_errors="ignore") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in remaining_rows:
                    writer.writerow({k: r.get(k, "") for k in fieldnames})

        except Exception as e:
            print("❌ sender loop crashed:", e)

        await asyncio.sleep(60)


# -------------------------------------------------
# AI reminder generator loop
# -------------------------------------------------
async def run_reminder_engine_loop():
    while True:
        try:
            run_reminder_ai()
        except Exception as e:
            print("❌ reminder engine crashed:", e)

        await asyncio.sleep(60)


# -------------------------------------------------
# ✅ NEW: periodic Google Tasks → CSV sync loop
# -------------------------------------------------
async def sync_google_tasks_loop():
    """
    Every 60 seconds, sync all onboarded users
    from Google Tasks into tasks.csv
    """
    while True:
        try:
            if not os.path.exists(DATABASE_FILE):
                await asyncio.sleep(60)
                continue

            with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)

            for user_key, data in db.items():

                # very light guard: must look like a real user entry
                # and must already be onboarded
                if not isinstance(data, dict):
                    continue

                # if user has no auth info yet, skip
                # (your ayth_script will raise if not registered anyway)
                try:
                    count = sync_user_tasks_to_csv(user_key)
                    print(f"🔄 synced {count} tasks for {user_key}")
                except Exception as e:
                    print(f"❌ sync failed for {user_key}: {e}")

        except Exception as e:
            print("❌ sync loop crashed:", e)

        await asyncio.sleep(60)


# -------------------------------------------------
# Main
# -------------------------------------------------
def main():
    import nest_asyncio
    nest_asyncio.apply()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("connect", handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Telegram bot running with reminders and background sync...")

    async def start_background_tasks():
        asyncio.create_task(run_reminder_engine_loop())
        asyncio.create_task(send_reminders_loop(app))
        asyncio.create_task(sync_google_tasks_loop())   # ✅ new

    asyncio.get_event_loop().create_task(start_background_tasks())

    app.run_polling()


if __name__ == "__main__":
    main()
