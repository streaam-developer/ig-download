"""
Telegram Mega Folder Video Downloader & Uploader (megadl only)
- Recursively downloads all files from a MEGA folder using megadl
- Uploads each file to Telegram
- Deletes file after successful upload
- Shows upload progress

Requirements
- Python 3.10+
- pip install pyrogram tgcrypto aiofiles tqdm
- megadl installed and working
"""

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path
import time
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message

# ---------------- CONFIG ----------------
API_ID = int(os.environ.get("API_ID", "27074109"))
API_HASH = os.environ.get("API_HASH", "301e069d266e091df4bd58353679f3b1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8292399578:AAH2jrVBWHnCTLCsEr7pcCZF89XqxPCkKRY")
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", "6471788911"))
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "./downloads")
VIDEO_EXTS = {"mp4", "mkv", "avi", "mov", "flv", "webm", "ts"}

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

import re

MEGA_LINK_RE = r"https?://(?:www\.)?mega\.nz/(?:folder|file|#!|#F!)/[A-Za-z0-9_-]+(?:#[A-Za-z0-9_-]+)?"

text = message.text.strip()
links = re.findall(MEGA_LINK_RE, text)

if not links:
    await message.reply_text("Send a valid MEGA folder/file link.")
    return
# ---------------- UTILS ----------------
async def progress_bar(current, total, message: Message, start_time, filename):
    now = time.time()
    diff = max(now - start_time, 1)
    percentage = current * 100 / total if total else 0
    speed = current / diff
    eta = (total - current) / speed if speed > 0 else 0
    bar_length = 20
    filled = int(bar_length * percentage / 100)
    bar = "█" * filled + "—" * (bar_length - filled)
    text = (
        f"{filename}\n[{bar}] {percentage:.1f}%\n"
        f"{current//1024//1024}/{total//1024//1024} MB\n"
        f"Speed: {speed/1024:.2f} KB/s | ETA: {int(eta)}s"
    )
    try:
        await message.edit_text(text)
    except Exception:
        pass


async def upload_and_cleanup(client: Client, chat_id: int, file_path: Path, status_msg: Message):
    try:
        start = time.time()
        await client.send_document(
            chat_id,
            document=str(file_path),
            caption=file_path.name.replace("@BabaJiMega", "").strip(),
            progress=progress_bar,
            progress_args=(status_msg, start, file_path.name),
        )
        try:
            file_path.unlink()
        except Exception:
            pass
    except Exception as e:
        await status_msg.edit_text(f"Failed {file_path.name}: {e}")


async def download_mega_folder(link: str, dest_folder: Path):
    """Use megadl to download entire folder recursively"""
    dest_folder.mkdir(parents=True, exist_ok=True)
    cmd = ["megadl", "--path", str(dest_folder), link]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        print("megadl error:", proc.stderr)
    files = []
    for f in dest_folder.rglob("*"):
        if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTS:
            files.append(f)
    return files


# ---------------- APP INIT ----------------
if BOT_TOKEN:
    app = Client("mega_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
else:
    app = Client("mega_user", api_id=API_ID, api_hash=API_HASH)

# ---------------- HANDLER ----------------
@app.on_message(filters.private & filters.text)
async def on_message(client: Client, message: Message):
    if ALLOWED_USER_ID and message.from_user and message.from_user.id != ALLOWED_USER_ID:
        return

    text = message.text.strip()
    import re
    links = re.findall(MEGA_LINK_RE, text)
    if not links:
        await message.reply_text("Send a valid MEGA folder/file link.")
        return

    await message.reply_text(f"Found {len(links)} link(s). Starting download...")

    for link in links:
        tmp_dir = Path(tempfile.mkdtemp(prefix="mega_dl_", dir=DOWNLOAD_DIR))
        try:
            files = await download_mega_folder(link, tmp_dir)
            if not files:
                await message.reply_text("No video files found in this folder.")
                continue
            files.sort()
            for f in files:
                status = await message.reply_text(f"Uploading {f.name}...")
                await upload_and_cleanup(client, message.chat.id, f, status)
                await status.edit_text(f"Uploaded {f.name} ✅")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    await message.reply_text("All done!")


# ---------------- MAIN ----------------
if __name__ == "__main__":
    if API_ID == 0 or not API_HASH:
        print("ERROR: Set API_ID and API_HASH")
        sys.exit(1)
    print("Starting Mega-only video bot...")
    app.run()
