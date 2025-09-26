import os
import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import ChatJoinRequest
from pyrogram.errors import ChatAdminRequired, FloodWait, BadRequest, Forbidden, UserNotParticipant

# Set up logging for full debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),  # Logs to file
        logging.StreamHandler()  # Also prints to console
    ]
)
logger = logging.getLogger(__name__)

# Environment variables (as provided)
API_ID = int(os.environ.get("API_ID", "27074109"))
API_HASH = os.environ.get("API_HASH", "301e069d266e091df4bd58353679f3b1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8292399578:AAH2jrVBWHnCTLCsEr7pcCZF89XqxPCkKRY")
AUTH_CHANNEL = int(os.environ.get("CHANNEL_ID", "-1003087895191"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7006516881"))

logger.info(f"Loaded config: API_ID={API_ID}, AUTH_CHANNEL={AUTH_CHANNEL}, ADMIN_ID={ADMIN_ID}")

# Bot Client only (no user client)
bot = Client(
    "bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# In-memory storage for pending user IDs (only new requests while bot is running)
# For persistence, consider using a file, database (e.g., SQLite), or Redis
pending_user_ids = set()

@bot.on_chat_join_request(filters.chat(AUTH_CHANNEL))
async def handle_new_join_request(client, join_request: ChatJoinRequest):
    """
    Automatically captures new pending join requests and stores user IDs.
    This runs in real-time when a new request arrives.
    Note: This does NOT fetch existing pending requests before the bot started.
    """
    try:
        user_id = join_request.from_user.id
        pending_user_ids.add(user_id)
        logger.info(f"New pending request captured from user ID: {user_id} (Total pending: {len(pending_user_ids)})")
        print(f"New pending request from user ID: {user_id}")  # Console log as before
        # Optional: Auto-approve or decline here if needed
        # await client.approve_chat_join_request(AUTH_CHANNEL, user_id, join_request.date)
        # Or: await client.decline_chat_join_request(AUTH_CHANNEL, user_id, join_request.date)
    except Exception as e:
        logger.error(f"Error in handle_new_join_request: {str(e)}")
        print(f"Error handling new join request: {e}")

@bot.on_message(filters.command("check") & filters.user(ADMIN_ID))
async def check_pending_requests(client, message):
    """
    Handles /check command - only for ADMIN_ID.
    Logs every step for debugging.
    """
    try:
        logger.info(f"/check command received from user {message.from_user.id} in chat {message.chat.id}")
        print(f"/check triggered by user {message.from_user.id}")
        
        await message.reply("Checking pending join requests (new ones captured by bot)...")
        logger.info("Replied with 'Checking...' message")
        
        if pending_user_ids:
            id_list = "\n".join(str(uid) for uid in sorted(pending_user_ids))
            response = f"Total Pending User IDs ({len(pending_user_ids)}):\n{id_list}"
            await message.reply(response)
            logger.info(f"Sent response with {len(pending_user_ids)} pending IDs")
            print(f"Response sent: {len(pending_user_ids)} IDs listed")
        else:
            no_pending_msg = "No pending join requests captured yet. (Bot only tracks new ones after startup.)"
            await message.reply(no_pending_msg)
            logger.info("Sent 'No pending' response")
            print("No pending requests - response sent")
            
    except BadRequest as e:
        # Common: Message too long, or reply failed
        logger.warning(f"BadRequest in /check: {str(e)} (e.g., message too long or can't reply)")
        print(f"BadRequest: {e}")
        # Fallback: Send a short message
        try:
            await message.reply("Pending requests found, but response too long. Check logs for details.")
        except:
            pass
    except Forbidden as e:
        logger.error(f"Forbidden in /check: {str(e)} (Bot can't send messages here)")
        print(f"Forbidden: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in check_pending_requests: {str(e)}")
        print(f"Full error in /check: {e}")
        try:
            await message.reply(f"Error: {str(e)}")
        except:
            pass

# General message handler for debugging incoming messages (logs all commands)
@bot.on_message(filters.command(["start", "help", "check"]))
async def log_all_commands(client, message):
    """
    Logs ALL incoming commands for debugging (even if not handled elsewhere).
    This helps see if /check is being received at all.
    """
    try:
        logger.info(f"Incoming command '{message.command[0]}' from user {message.from_user.id} (username: {message.from_user.username or 'None'}) in chat {message.chat.id} (type: {message.chat.type})")
        print(f"Command logged: {message.command[0]} from {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error logging command: {str(e)}")

async def main():
    try:
        # Start the bot
        logger.info("Starting bot...")
        print("Starting bot...")
        await bot.start()
        me = await bot.get_me()
        logger.info(f"Bot started successfully! Bot username: @{me.username}, ID: {me.id}")
        print(f"Bot started! Username: @{me.username}, Listening for new join requests in channel {AUTH_CHANNEL}.")
        print("Use /check in a chat with the bot (only admin {ADMIN_ID} can use it).")
        print("Note: This bot can only track NEW pending requests after it starts. For full list including existing ones, a user client is required.")
        
        # Test if bot can access the channel
        try:
            channel = await bot.get_chat(AUTH_CHANNEL)
            logger.info(f"Bot can access channel: {channel.title} (ID: {channel.id})")
            print(f"Channel accessible: {channel.title}")
        except Exception as e:
            logger.warning(f"Bot cannot access channel {AUTH_CHANNEL}: {str(e)} (Ensure bot is admin)")
            print(f"Warning: Cannot access channel - {e}")
        
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        print(f"Bot start failed: {e}")
        return
    
    try:
        # Keep the bot running
        logger.info("Bot is now idle and running...")
        print("Bot is running. Press Ctrl+C to stop.")
        await idle()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
        print("Bot stopped.")
    except Exception as e:
        logger.error(f"Error during idle: {str(e)}")
        print(f"Idle error: {e}")
    finally:
        await bot.stop()
        logger.info("Bot stopped.")
        print("Bot fully stopped.")

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
