# telegram_bot.py
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from muster_point import handle_user_message  # updated import

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN2")  # ensure this matches your .env

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message and instructions"""
    await update.message.reply_text(
        "Hi! I’m your personal assistant bot.\n\n"
        "To connect your Google Tasks account, send /connect\n"
        "After connecting, you can send tasks in this format:\n"
        "Task title | ISO due date\n\n"
        "Example:\nCall Mum | 2026-02-11T11:00:00Z"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all incoming messages and route to unified muster_point handler"""
    msg = update.message
    if not msg:
        return

    user_id = msg.from_user.id
    text = msg.text or msg.caption or ""

    # Send message to muster_point handler
    response_dict = handle_user_message(user_id=user_id, message_text=text)

    # Reply to user
    reply = response_dict.get("message", "🤖 Something went wrong.")
    await msg.reply_text(reply)


# --- Main ---
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("connect", handle_message))  # /connect goes through same handler

    # All other text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Telegram bot running...")
    app.run_polling()
