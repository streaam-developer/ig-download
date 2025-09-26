import os
import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import ChatJoinRequest, Message
from pyrogram.errors import BadRequest, Forbidden, PeerIdInvalid

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot.log")]
)
logger = logging.getLogger(__name__)

# Load environment variables
API_ID = int(os.environ.get("API_ID", "27074109"))
API_HASH = os.environ.get("API_HASH", "301e069d266e091df4bd58353679f3b1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8292399578:AAH2jrVBWHnCTLCsEr7pcCZF89XqxPCkKRY")
AUTH_CHANNEL = int(os.environ.get("CHANNEL_ID", "-1003087895191"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7006516881"))

# Bot client
bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# In-memory store of pending user IDs
pending_user_ids = set()

@bot.on_chat_join_request(filters.chat(AUTH_CHANNEL))
async def handle_new_join_request(client, join_request: ChatJoinRequest):
    user_id = join_request.from_user.id
    pending_user_ids.add(user_id)
    logger.info(f"New join request: {user_id}")
    print(f"[JOIN REQUEST] User ID: {user_id}")

# Log all messages
@bot.on_message()
async def log_all_messages(client, message: Message):
    try:
        logger.debug(f"[MSG] From: {message.from_user.id if message.from_user else 'None'} | "
                     f"Chat: {message.chat.id} | Text: {message.text or 'Media'}")
    except Exception as e:
        logger.error(f"Message log error: {e}")

# /start command (works in private and group)
@bot.on_message(filters.command("start", prefixes=["/", "!"]))
async def start_command(client, message: Message):
    try:
        await message.reply("✅ Bot is working! Use /check or /ping (admin only).\nUse /help to see all commands.")
        logger.info(f"/start from {message.from_user.id}")
    except Exception as e:
        logger.error(f"/start error: {e}")

# /help command
@bot.on_message(filters.command("help", prefixes=["/", "!"]))
async def help_command(client, message: Message):
    try:
        text = (
            "🤖 **Bot Commands**:\n"
            "/start - Test bot is online\n"
            "/help - Show this help message\n"
            "/ping - Check bot status (admin only)\n"
            "/check - Show pending join requests (admin only)"
        )
        await message.reply(text)
    except Exception as e:
        logger.error(f"/help error: {e}")

# /check command - ADMIN ONLY
@bot.on_message(filters.command("check", prefixes=["/", "!"]) & filters.user(ADMIN_ID))
async def check_pending_requests(client, message: Message):
    try:
        if pending_user_ids:
            id_list = "\n".join(str(uid) for uid in sorted(pending_user_ids))
            response = f"📋 **Pending Requests** ({len(pending_user_ids)}):\n{id_list}"
            if len(response) > 4096:
                await message.reply("Too many pending requests to display. Check the log file.")
            else:
                await message.reply(response)
        else:
            await message.reply("✅ No pending join requests yet.")
        logger.info(f"/check by admin: {message.from_user.id}")
    except Exception as e:
        logger.error(f"/check error: {e}")
        await message.reply(f"Error: {str(e)}")

# /ping command - ADMIN ONLY
@bot.on_message(filters.command("ping", prefixes=["/", "!"]) & filters.user(ADMIN_ID))
async def ping_command(client, message: Message):
    try:
        await message.reply("🏓 Pong! Bot is alive.")
        logger.info(f"/ping by admin: {message.from_user.id}")
    except Exception as e:
        logger.error(f"/ping error: {e}")

# Fallback for unknown commands or text
@bot.on_message(filters.text & ~filters.command(["start", "help", "check", "ping"]))
async def fallback_handler(client, message: Message):
    try:
        await message.reply("❓ Unknown command. Use /help to see available commands.")
    except Exception as e:
        logger.warning(f"Fallback reply failed: {e}")

# Main function
async def main():
    try:
        await bot.start()
        me = await bot.get_me()
        print(f"✅ Bot started: @{me.username} (ID: {me.id})")
        print(f"🔍 Monitoring join requests in: {AUTH_CHANNEL}")
        try:
            channel = await bot.get_chat(AUTH_CHANNEL)
            print(f"✅ Channel found: {channel.title} ({channel.id})")
        except PeerIdInvalid:
            print(f"❌ Invalid channel ID: {AUTH_CHANNEL}")
        except Exception as e:
            print(f"⚠️ Can't access channel: {e}")
        # Self test message
        try:
            test_msg = await bot.send_message("me", "🤖 Bot is running.")
            await asyncio.sleep(2)
            await bot.delete_messages("me", test_msg.id)
        except Exception as e:
            print(f"⚠️ Self-message test failed: {e}")
        await idle()
    except KeyboardInterrupt:
        print("🛑 Bot stopped manually.")
    finally:
        await bot.stop()
        print("✅ Bot fully stopped.")

if __name__ == "__main__":
    asyncio.run(main())
