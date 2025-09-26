import os
from pyrogram import Client, filters
from pyrogram.errors import RPCError, UserNotParticipant

# --- Config ---
API_ID = int(os.environ.get("API_ID", "27074109"))
API_HASH = os.environ.get("API_HASH", "301e069d266e091df4bd58353679f3b1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8292399578:AAH2jrVBWHnCTLCsEr7pcCZF89XqxPCkKRY")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003087895191"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7006516881"))

app = Client("joinreq_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


def is_member_status(status: str) -> bool:
    """Return True if status indicates the user is joined/approved."""
    if not status:
        return False
    status = status.lower()
    return status in ("member", "administrator", "creator")


# /start -> create join-request link
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    try:
        invite = await client.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            creates_join_request=True  # force join-request link
        )
        await message.reply_text(
            f"✅ यहाँ तुम्हारा join-request link है:\n\n{invite.invite_link}\n\n"
            "इससे join करने के बाद admin approve करेंगे।"
        )
    except RPCError as e:
        await message.reply_text(
            "❌ Join-request link नहीं बना सका।\n\n"
            "Bot को channel का admin बनाओ और 'Invite Users via Link' permission दो।"
        )
        print("create_chat_invite_link error:", e)


# /check -> check if approved member
@app.on_message(filters.command("check") & filters.private)
async def check_handler(client, message):
    user_id = message.from_user.id
    try:
        member = await client.get_chat_member(CHANNEL_ID, user_id)
        if is_member_status(getattr(member, "status", None)):
            await message.reply_text("✅ तुम्हारी request approve हो गई है, तुम channel member हो।")
        else:
            await message.reply_text("❌ Request अभी approve नहीं हुई।")
    except UserNotParticipant:
        await message.reply_text("❌ तुम्हारी request अभी तक approve नहीं हुई (pending है या send ही नहीं की)।")
    except RPCError as e:
        await message.reply_text("⚠️ Error आया, bot शायद channel में admin नहीं है।")
        print("get_chat_member error:", e)


# सिर्फ admin नया link बना सके
@app.on_message(filters.command("newlink") & filters.user(ADMIN_ID))
async def newlink_handler(client, message):
    try:
        invite = await client.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            creates_join_request=True
        )
        await message.reply_text(f"🔐 नया join-request link:\n\n{invite.invite_link}")
    except RPCError as e:
        await message.reply_text("❌ नया link नहीं बना सका।")
        print("newlink error:", e)


if __name__ == "__main__":
    print("Bot is running...")
    app.run()
