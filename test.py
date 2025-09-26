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
    if not status:
        return False
    status = status.lower()
    return status in ("member", "administrator", "creator")


# /start -> join-request link
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    try:
        invite = await client.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            creates_join_request=True
        )
        await message.reply_text(
            f"👉 यहाँ तुम्हारा join-request link है:\n\n{invite.invite_link}\n\n"
            "Request भेजो, फिर /check से status देख सकते हो।"
        )
    except RPCError as e:
        await message.reply_text("❌ Join-request link बनाने में error आया।\nBot को channel का admin बनाओ।")
        print("create_chat_invite_link error:", e)


# /check -> member / pending / not sent
@app.on_message(filters.command("check") & filters.private)
async def check_handler(client, message):
    user_id = message.from_user.id
    try:
        # 1) पहले check करें approved member है या नहीं
        member = await client.get_chat_member(CHANNEL_ID, user_id)
        if is_member_status(getattr(member, "status", None)):
            await message.reply_text("✅ तुम्हारी request approve हो चुकी है, तुम channel member हो।")
            return
    except UserNotParticipant:
        pass  # अगर member नहीं है तो नीचे pending check करेंगे
    except RPCError as e:
        await message.reply_text("⚠️ Error: bot शायद channel का admin नहीं है।")
        print("get_chat_member error:", e)
        return

    # 2) अगर member नहीं है, तो pending list check करो
    try:
        pending_requests = await client.get_chat_join_requests(CHANNEL_ID, limit=200)
        if any(req.from_user.id == user_id for req in pending_requests):
            await message.reply_text("⌛ तुम्हारी request अभी PENDING है, admin के approval का इंतज़ार है।")
        else:
            await message.reply_text("❌ तुम्हारी request pending में नहीं है (शायद भेजी ही नहीं या reject हो गई)।")
    except RPCError as e:
        await message.reply_text("⚠️ Pending requests check करने में error आया।")
        print("get_chat_join_requests error:", e)


if __name__ == "__main__":
    print("Bot is running...")
    app.run()
