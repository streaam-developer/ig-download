import os
import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import ChatJoinRequest, Message
from pyrogram.errors import BadRequest, Forbidden

# ========== CONFIG ==========

API_ID = int(os.environ.get("API_ID", "27074109"))
API_HASH = os.environ.get("API_HASH", "301e069d266e091df4bd58353679f3b1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8292399578:AAH2jrVBWHnCTLCsEr7pcCZF89XqxPCkKRY")
AUTH_CHANNEL = int(os.environ.get("CHANNEL_ID", "-1003087895191"))  # Optional
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7006516881"))  # Replace with your own Telegram ID

# ========== LOGGING ==========

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot.log")]
)
logger = logging.getLogger(__name__)

# ========== INIT BOT ==========

bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# In-memory pending list
pending_user_ids = set()

# ========== JOIN REQUEST HANDLER (OPTIONAL) ==========

@bot.on_chat_join_request(filters.chat(AUTH_CHANNEL))
async def handle_join_request(client, join_request: ChatJoinRequest):
    user_id = join_request.from_user.id
    pending_user_ids.add(user_id)
    print(f"[JOIN REQUEST] New request from: {user_id}")
    logger.info(f"Join request from {user_id}")

# ========== /start ==========

@bot.on_message(filters.private & filters.command("start"))
async def start_command(client, message: Message):
    print(f"[CMD] /start from {message.from_user.id}")
    await message.reply("✅ Hello! I'm alive.\nUse /help for commands.")

# ========== /help ==========

@bot.on_message(filters.private & filters.command("help"))
async def help_command(client, message: Message):
    await message.reply(
        "**🤖 Bot Commands:**\n"
        "/start - Check bot status\n"
        "/help - Show this help message\n"
        "/ping - Check if bot is online (admin only)\n"
        "/check - See pending join requests (admin only)"
    )

# ========== /ping (admin only) ==========

@bot.on_message(filters.private & filters.command("ping") & filters.user(ADMIN_ID))
async def ping_command(client, message: Message):
    await message.reply("🏓 Pong! Bot is responsive.")

# ========== /check (admin only) ==========

@bot.on_message(filters.private & filters.command("check") & filters.user(ADMIN_ID))
async def check_command(client, message: Message):
    if pending_user_ids:
        response = "**Pending Join Requests:**\n" + "\n".join(str(uid) for uid in pending_user_ids)
        if len(response) > 4096:
            await message.reply("Too many to list. Check the bot.log file.")
        else:
            await message.reply(response)
    else:
        await message.reply("✅ No pending join requests captured.")

# ========== /id (for debug) ==========

@bot.on_message(filters.private & filters.command("id"))
async def id_command(client, message: Message):
    await message.reply(f"🆔 Your Telegram ID: `{message.from_user.id}`")

# ========== LOG ALL MESSAGES ==========

@bot.on_message(filters.private)
async def log_all_messages(client, message: Message):
    logger.debug(f"[MSG] From {message.from_user.id}: {message.text}")
    print(f"[DEBUG] DM from {message.from_user.id}: {message.text}")

# ========== MAIN ==========

async def main():
    await bot.start()
    me = await bot.get_me()
    print(f"✅ Bot started: @{me.username} (ID: {me.id})")

    # Test channel access
    try:
        channel = await bot.get_chat(AUTH_CHANNEL)
        print(f"✅ Channel found: {channel.title} ({channel.id})")
    except Exception as e:
        print(f"⚠️ Warning: Cannot access channel {AUTH_CHANNEL}: {e}")

    print("💬 Waiting for messages in private chat (DM)...")
    await idle()
    await bot.stop()
    print("✅ Bot stopped.")

if __name__ == "__main__":
    asyncio.run(main())
