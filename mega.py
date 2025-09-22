"""
Telegram Mega Folder Video Downloader & Uploader (with progress bars)
- Works in both Userbot mode (Pyrogram Client with session) and Bot mode (Bot Token)
- Downloads video files from MEGA folder link one by one
- Shows upload progress per file with progress bar in Telegram message
- Deletes local file after successful upload

Requirements
- Python 3.10+
- pip install pyrogram tgcrypto mega.py python-magic aiofiles tqdm
- Optional: install `megadl` from megatools/megacmd if mega.py fails

Config (env vars)
- API_ID, API_HASH: from https://my.telegram.org
- SESSION_NAME (optional, for userbot)
- BOT_TOKEN (if running in bot mode)
- ALLOWED_USER_ID (Telegram numeric id of owner)
"""

import asyncio
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List
import time

from pyrogram import Client, filters
from pyrogram.types import Message

try:
    from mega import Mega
except Exception:
    Mega = None

import subprocess

API_ID = int(os.environ.get("API_ID", "27074109"))
API_HASH = os.environ.get("API_HASH", "301e069d266e091df4bd58353679f3b1")
SESSION_NAME = os.environ.get("SESSION_NAME", "mega_video_session")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8292399578:AAH2jrVBWHnCTLCsEr7pcCZF89XqxPCkKRY")
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", "6471788911"))
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "./downloads")
VIDEO_EXTS = {"mp4", "mkv", "avi", "mov", "flv", "webm", "ts"}
CONCURRENT_JOBS = int(os.environ.get("CONCURRENT_JOBS", "2"))

MEGA_FOLDER_RE = re.compile(r"https?://(?:www\.)?mega\.nz/(?:folder|#F!)/[A-Za-z0-9_-]+(?:!?[A-Za-z0-9_-]+)?")
MEGA_FILE_RE = re.compile(r"https?://(?:www\.)?mega\.nz/(?:file|#!|#F!)[A-Za-z0-9_-]+")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def get_mega_client():
    if Mega is None:
        return None
    m = Mega()
    try:
        return m.login()
    except Exception:
        return m


async def download_from_mega_link(link: str, dest_folder: Path) -> List[Path]:
    dest_folder.mkdir(parents=True, exist_ok=True)
    downloaded: List[Path] = []
    m = get_mega_client()
    if m:
        try:
            if hasattr(m, "download_url"):
                result = m.download_url(link, str(dest_folder))
            elif hasattr(m, "download"):
                result = m.download(link, str(dest_folder))
            else:
                result = None

            if result:
                paths = result if isinstance(result, (list, tuple)) else [result]
                for p in paths:
                    pth = Path(p)
                    if pth.is_file():
                        downloaded.append(pth)
                    elif pth.is_dir():
                        for f in pth.rglob('*'):
                            if f.is_file():
                                downloaded.append(f)
                downloaded = [p for p in downloaded if p.suffix.lstrip('.').lower() in VIDEO_EXTS]
                if downloaded:
                    return downloaded
        except Exception as e:
            print("mega.py failed:", e)

    try:
        print("Falling back to megadl...")
        cmd = ["megadl", "--path", str(dest_folder), link]
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode == 0:
            for f in Path(dest_folder).rglob('*'):
                if f.is_file() and f.suffix.lstrip('.').lower() in VIDEO_EXTS:
                    downloaded.append(f)
            return downloaded
        else:
            print("megadl failed:", proc.stderr)
    except Exception as e:
        print("megadl error:", e)

    return downloaded


async def progress_bar(current, total, message: Message, start_time, filename):
    now = time.time()
    diff = now - start_time
    if diff == 0:
        diff = 1
    percentage = current * 100 / total if total else 0
    speed = current / diff
    eta = (total - current) / speed if speed > 0 else 0
    bar_length = 20
    filled = int(bar_length * percentage / 100)
    bar = "█" * filled + "—" * (bar_length - filled)
    text = f"{filename}\n[{bar}] {percentage:.1f}%\n{current//1024//1024}/{total//1024//1024} MB\nSpeed: {speed/1024:.2f} KB/s | ETA: {int(eta)}s"
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
            caption=file_path.name,
            progress=progress_bar,
            progress_args=(status_msg, start, file_path.name)
        )
        try:
            file_path.unlink()
        except Exception:
            pass
    except Exception as e:
        await status_msg.edit_text(f"Failed {file_path.name}: {e}")


if BOT_TOKEN:
    app = Client("mega_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
else:
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

semaphore = asyncio.Semaphore(CONCURRENT_JOBS)


@app.on_message(filters.private & filters.text)
async def on_message(client: Client, message: Message):
    if ALLOWED_USER_ID and message.from_user and message.from_user.id != ALLOWED_USER_ID:
        return

    text = message.text.strip()
    links = MEGA_FOLDER_RE.findall(text) + MEGA_FILE_RE.findall(text)
    if not links:
        await message.reply_text("Send a valid MEGA folder/file link.")
        return

    await message.reply_text(f"Got {len(links)} link(s). Starting...")

    async with semaphore:
        for link in links:
            tmp_dir = Path(tempfile.mkdtemp(prefix="mega_dl_", dir=DOWNLOAD_DIR))
            try:
                files = await download_from_mega_link(link, tmp_dir)
                if not files:
                    await message.reply_text("No videos found in link.")
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    continue
                files.sort()
                for f in files:
                    status = await message.reply_text(f"Uploading {f.name}...")
                    await upload_and_cleanup(client, message.chat.id, f, status)
                    await status.edit_text(f"Uploaded {f.name} ✅")
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
    await message.reply_text("All done.")


if __name__ == '__main__':
    if API_ID == 0 or not API_HASH:
        print("ERROR: Set API_ID and API_HASH")
        sys.exit(1)
    print("Starting Mega video bot...")
    app.run()
