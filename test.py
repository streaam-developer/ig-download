import os
import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import ChatJoinRequest, Message
from pyrogram.errors import ChatAdminRequired, FloodWait, BadRequest, Forbidden, UserNotParticipant, PeerIdInvalid

# Set up logging for full debugging (more verbose)
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more details
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
pending_user_ids = set()

@bot.on_chat_join_request(filters.chat(AUTH_CHANNEL))
async def handle_new_join_request(client, join_request: ChatJoinRequest):
    """
    Automatically captures new pending join requests and stores user IDs.
    """
    try:
        user_id = join_request.from_user.id
        pending_user_ids.add(user_id)
        logger.info(f"New pending request captured from user ID: {user_id} (Total pending: {len(pending_user_ids)})")
        print(f"New pending request from user ID: {user_id}")
    except Exception as e:
        logger.error(f"Error in handle_new_join_request: {str(e)}")
        print(f"Error handling new join request: {e}")

# General handler to log ALL incoming messages (for debugging why commands aren't received)
@bot.on_message()
async def log_all_messages(client, message: Message):
    """
    Logs EVERY incoming message to the bot. This will show if messages are reaching the bot at all.
    """
    try:
        logger.debug(f"ALL MESSAGE RECEIVED: From user {message.from_user.id if message.from_user else 'None'} (username: {message.from_user.username if message.from_user else 'None'}), "
                     f"Chat ID: {message.chat.id}, Chat Type: {message.chat.type}, Text: '{message.text or 'Non-text message'}', "
                     f"Is Command: {message.text.startswith('/') if message.text else False}")
        print(f"[DEBUG] Message received in chat {message.chat.id} from {message.from_user.id if message.from_user else 'Unknown'}: {message.text or 'Media/Other'}")
    except Exception as e:
        logger.error(f"Error logging all messages: {str(e)}")

# Basic /start handler - replies to ANYONE to test if bot can respond
@bot.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """
    Simple /start to test bot responsiveness. Replies to anyone.
    """
    try:
        logger.info(f"/start command received from user {message.from_user.id} in chat {message.chat.id}")
        print(f"/start triggered by user {message.from_user.id}")
        
        await message.reply("Bot is working! Hello from @Boltarhegabot. Use /check for pending requests (admin only).")
        logger.info("Replied to /start")
        print("Replied to /start")
    except Exception as e:
        logger.error(f"Error in /start: {str(e)}")
        print(f"Error in /start: {e}")

# Log all commands (expanded to more commands for testing)
@bot.on_message(filters.command(["help", "check", "ping"]))
async def log_all_commands(client, message: Message):
    """
    Logs incoming commands like /help, /check, /ping for debugging.
    """
    try:
        cmd = message.command[0] if message.command else "unknown"
        logger.info(f"Incoming command '{cmd}' from user {message.from_user.id} (username: {message.from_user.username or 'None'}) "
                    f"in chat {message.chat.id} (type: {message.chat.type})")
        print(f"Command logged: /{cmd} from {message.from_user.id} in {message.chat.type}")
    except Exception as e:
        logger.error(f"Error logging command: {str(e)}")

@bot.on_message(filters.command("check") & filters.user(ADMIN_ID))
async def check_pending_requests(client, message: Message):
    """
    Handles /check command - only for ADMIN_ID.
    """
    try:
        logger.info(f"/check command received from admin {message.from_user.id} in chat {message.chat.id}")
        print(f"/check triggered by admin {message.from_user.id}")
        
        await message.reply("Checking pending join requests (new ones captured by bot)...")
        logger.info("Replied with 'Checking...' message")
        
        if pending_user_ids:
            id_list = "\n".join(str(uid) for uid in sorted(pending_user_ids))
            response = f"Total Pending User IDs ({len(pending_user_ids)}):\n{id_list}"
            # Check if response is too long
            if len(response) > 4096:
                response = f"Total Pending: {len(pending_user_ids)}. Too many to list here. Check bot.log or console."
            await message.reply(response)
            logger.info(f"Sent /check response with {len(pending_user_ids)} pending IDs")
            print(f"/check response sent: {len(pending_user_ids)} IDs")
        else:
            no_pending_msg = "No pending join requests captured yet. (Bot only tracks new ones after startup.)"
            await message.reply(no_pending_msg)
            logger.info("Sent 'No pending' response")
            print("No pending requests - /check response sent")
            
    except BadRequest as e:
        logger.warning(f"BadRequest in /check: {str(e)} (e.g., message too long or can't reply)")
        print(f"BadRequest in /check: {e}")
        try:
            await message.reply("Pending requests found, but response too long. Check logs.")
        except:
            pass
    except Forbidden as e:
        logger.error(f"Forbidden in /check: {str(e)} (Bot can't send messages here - check privacy or add bot)")
        print(f"Forbidden in /check: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in /check: {str(e)}")
        print(f"Full error in /check: {e}")
        try:
            await message.reply(f"Error: {str(e)}")
        except:
            pass

# Optional: /ping for testing latency/response
@bot.on_message(filters.command("ping") & filters.user(ADMIN_ID))
async def ping_command(client, message: Message):
    """
    Simple /ping for admin to test if commands work.
    """
    try:
        start_time = message.date
        await message.reply("Pong! Bot is responsive.")
        logger.info(f"/ping from admin {message.from_user.id}")
        print("/ping responded")
    except Exception as e:
        logger.error(f"Error in /ping: {str(e)}")

async def main():
    try:
        logger.info("Starting bot...")
        print("Starting bot...")
        await bot.start()
        me = await bot.get_me()
        logger.info(f"Bot started successfully! Bot username: @{me.username}, ID: {me.id}")
        print(f"Bot started! Username: @{me.username}, ID: {me.id}")
        print(f"Listening for new join requests in channel {AUTH_CHANNEL}.")
        print("Test commands:")
        print("- Send /start to bot in DMs to test basic reply.")
        print("- Send /check or /ping from ADMIN_ID (7006516881) in DMs or group.")
        print("Note: For commands in GROUPS, disable bot privacy: /mybots > @Boltarhegabot > Bot Settings > Group Privacy > Turn off.")
        
        # Test channel access
        try:
            channel = await bot.get_chat(AUTH_CHANNEL)
            logger.info(f"Bot can access channel: {channel.title} (ID: {channel.id}, Type: {channel.type})")
            print(f"Channel accessible: {channel.title} (Type: {channel.type})")
        except PeerIdInvalid:
            logger.error(f"Invalid channel ID: {AUTH_CHANNEL}. Check if it's correct (should be negative for channels).")
            print(f"ERROR: Invalid channel ID {AUTH_CHANNEL}")
        except Exception as e:
            logger.warning(f"Bot cannot access channel {AUTH_CHANNEL}: {str(e)} (Ensure bot is admin in channel)")
            print(f"Warning: Cannot access channel - {e}. Add bot as admin.")
        
        # Test sending a message to self (DM) to verify reply capability
        try:
            test_msg = await bot.send_message("me", "Bot self-test: Running successfully!")
            logger.info(f"Self-test message sent to 'me' (ID: {test_msg.id})")
            print("Self-test: Bot can send messages.")
            await asyncio.sleep(2)
            await bot.delete_messages("me", test_msg.id)  # Clean up
        except Exception as e:
            logger.warning(f"Self-test failed: {str(e)} (Bot may have issues sending messages)")
            print(f"Self-test warning: {e}")
        
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        print(f"Bot start failed: {e}")
        return
    
    try:
        logger.info("Bot is now idle and running...")
        print("Bot is running. Press Ctrl+C to stop.")
        print("Send /start to bot in DMs to test. Watch console/logs for [DEBUG] messages.")
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
    asyncio.run(main())
