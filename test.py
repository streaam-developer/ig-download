import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import ChatJoinRequest
from pyrogram.errors import ChatAdminRequired, FloodWait

# Environment variables (as provided)
API_ID = int(os.environ.get("API_ID", "27074109"))
API_HASH = os.environ.get("API_HASH", "301e069d266e091df4bd58353679f3b1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8292399578:AAH2jrVBWHnCTLCsEr7pcCZF89XqxPCkKRY")
AUTH_CHANNEL = int(os.environ.get("CHANNEL_ID", "-1003087895191"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7006516881"))

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
    user_id = join_request.from_user.id
    pending_user_ids.add(user_id)
    print(f"New pending request from user ID: {user_id}")  # For logging
    # Optional: Auto-approve or decline here if needed
    # await client.approve_chat_join_request(AUTH_CHANNEL, user_id, join_request.date)
    # Or: await client.decline_chat_join_request(AUTH_CHANNEL, user_id, join_request.date)

@bot.on_message(filters.command("check") & filters.user(ADMIN_ID))
async def check_pending_requests(client, message):
    await message.reply("Checking pending join requests (new ones captured by bot)...")
    
    try:
        if pending_user_ids:
            id_list = "\n".join(str(uid) for uid in sorted(pending_user_ids))
            response = f"Total Pending User IDs ({len(pending_user_ids)}):\n{id_list}"
            await message.reply(response)
        else:
            await message.reply("No pending join requests captured yet. (Bot only tracks new ones after startup.)")
            
    except Exception as e:
        await message.reply(f"Error: {str(e)}")
        print(f"Full error: {e}")  # For debugging

async def main():
    # Start the bot
    await bot.start()
    print("Bot started! Listening for new join requests in the channel.")
    print("Use /check in a chat with the bot (only admin can use it).")
    print("Note: This bot can only track NEW pending requests after it starts. For full list including existing ones, a user client is required.")
    
    # Keep the bot running
    await idle()

if __name__ == "__main__":
    # Import idle if not already (Pyrogram provides it)
    from pyrogram import idle
    # Run the main function
    asyncio.run(main())
