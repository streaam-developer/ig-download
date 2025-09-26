import os
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserNotParticipant, RPCError

# --- Config ---
API_ID = int(os.environ.get("API_ID", "27074109"))
API_HASH = os.environ.get("API_HASH", "301e069d266e091df4bd58353679f3b1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8292399578:AAH2jrVBWHnCTLCsEr7pcCZF89XqxPCkKRY")

AUTH_CHANNEL = int(os.environ.get("CHANNEL_ID", "-1003087895191"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7006516881"))

REQUEST_TO_JOIN_MODE = True
TRY_AGAIN_BTN = True

# Simulated DB for join request tracking
join_db_storage = {}

def join_db():
    class DB:
        @staticmethod
        async def isActive():
            return True

        @staticmethod
        async def get_user(user_id):
            return join_db_storage.get(user_id)

        @staticmethod
        async def set_user(user_id):
            join_db_storage[user_id] = {"user_id": user_id}
    return DB

async def is_subscribed(bot, message):
    # check in DB
    try:
        user = await join_db().get_user(message.from_user.id)
        if user and user["user_id"] == message.from_user.id:
            return True
        # check approved member
        try:
            user_data = await bot.get_chat_member(AUTH_CHANNEL, message.from_user.id)
        except UserNotParticipant:
            return False
        except Exception:
            return False
        else:
            if user_data.status != enums.ChatMemberStatus.BANNED:
                return True
    except Exception:
        return False
    return False

app = Client("force_sub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# /start command
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    if AUTH_CHANNEL and not await is_subscribed(client, message):
        # generate join-request link
        try:
            if REQUEST_TO_JOIN_MODE:
                invite_link = await client.create_chat_invite_link(chat_id=AUTH_CHANNEL, creates_join_request=True)
            else:
                invite_link = await client.create_chat_invite_link(chat_id=AUTH_CHANNEL)
        except Exception as e:
            print(e)
            await message.reply_text("Make sure Bot is admin in Forcesub channel")
            return

        # save user in DB to simulate pending
        await join_db().set_user(message.from_user.id)

        # build buttons
        btn = [[InlineKeyboardButton("ʙᴀᴄᴋᴜᴘ ᴄʜᴀɴɴᴇʟ", url=invite_link.invite_link)]]
        if TRY_AGAIN_BTN:
            btn.append([InlineKeyboardButton("↻ ᴛʀʏ ᴀɢᴀɪɴ", url=f"https://t.me/{message.chat.username}?start=subscribe")])

        text = "**🕵️ You must join the backup channel first then try again!**"
        await client.send_message(
            chat_id=message.from_user.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return
    else:
        await message.reply_text("✅ You are already subscribed or request approved!")

# /check command
@app.on_message(filters.command("check") & filters.private)
async def check_cmd(client, message):
    if await is_subscribed(client, message):
        await message.reply_text("✅ You are subscribed / approved!")
    else:
        await message.reply_text("⌛ You are not subscribed yet (pending or not sent).")

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
