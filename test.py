"""
join_request_bot.py
Bot that generates join-request link and checks join request/member status.

Requirements:
    pip install pyrogram tgcrypto python-dotenv
Run:
    export BOT_TOKEN="123:ABC..."
    export CHANNEL_ID="-1001234567890"   # your private channel
    export ADMIN_ID="123456789"          # your Telegram user id (for error logs)
    python join_request_bot.py
"""

import os
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import traceback

from pyrogram import Client, filters, enums
from pyrogram.types import Message

# --- Load env vars ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8292399578:AAH2jrVBWHnCTLCsEr7pcCZF89XqxPCkKRY" )
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003087895191"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "7006516881"))
APP_NAME = "joinreq_direct"

if not BOT_TOKEN or not CHANNEL_ID or not ADMIN_ID:
    raise RuntimeError("BOT_TOKEN, CHANNEL_ID, ADMIN_ID env vars required")

# --- Logging setup ---
LOG_FILE = "joinreq_direct.log"
logger = logging.getLogger("joinreq_direct")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())

# --- Bot client ---
bot = Client(APP_NAME, bot_token=BOT_TOKEN, parse_mode="html")


async def send_error(e: Exception, context: str):
    """Send error details to ADMIN_ID and log to file."""
    tb = traceback.format_exc()
    msg = f"❌ <b>Error in {context}</b>\n\n<code>{e}</code>\n\n<pre>{tb}</pre>"
    logger.exception("Error in %s: %s", context, e)
    try:
        await bot.send_message(ADMIN_ID, msg)
    except Exception as send_err:
        logger.error("Failed to send error log to admin: %s", send_err)


# --- Commands ---

@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(c: Client, m: Message):
    try:
        # Generate invite link with join request enabled
        link = await c.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            creates_join_request=True,
            name="JoinRequestLink"
        )
        await m.reply_text(
            f"👋 Welcome!\n\nHere is your join request link:\n{link.invite_link}\n\n"
            "Use /check to verify your request/member status."
        )
        logger.info("Generated join link for user %s", m.from_user.id)
    except Exception as e:
        await send_error(e, "start_cmd")
        await m.reply_text("Error while generating invite link. Admin notified.")


@bot.on_message(filters.private & filters.command("check"))
async def check_cmd(c: Client, m: Message):
    try:
        user_id = m.from_user.id
        cm = await c.get_chat_member(CHANNEL_ID, user_id)
        status = cm.status

        # Convert enum to human-readable
        try:
            status_str = enums.ChatMemberStatus(status).name
        except Exception:
            status_str = str(status)

        if status_str in ["MEMBER", "ADMINISTRATOR", "OWNER"]:
            await m.reply_text(f"✅ You are already a <b>{status_str}</b> of the channel.")
        else:
            # If not member → Telegram does NOT give pending info via API
            await m.reply_text(
                "ℹ️ You are <b>not a member yet</b>.\n\n"
                "If you clicked the join link, your request is pending for admin approval."
            )

        logger.info("Checked status for user=%s: %s", user_id, status_str)
    except Exception as e:
        await send_error(e, "check_cmd")
        await m.reply_text("Error while checking status. Admin notified.")


# --- Startup ---
async def main():
    logger.info("Starting bot...")
    await bot.start()
    logger.info("Bot started. Waiting for commands...")
    await asyncio.Event().wait()


if name == "main":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Exited by user")
