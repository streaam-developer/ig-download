# Filename: auto_hls_uploader.py (with FTP upload)

import os
import base64
import random
import string
import requests
import yt_dlp
import subprocess
import shutil
from dotenv import load_dotenv
from urllib.parse import quote
from hashlib import sha256
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from ftplib import FTP

load_dotenv()

WP_SITE = os.getenv("WP_SITE", "https://skymovieshd.boutique/").rstrip('/')
WP_USER = os.getenv("WP_USER", "upload")
WP_PASS = os.getenv("WP_PASS", "GZ8U 9Dxd BGKm XmHW dMlF SExb")
SECRET_KEY = os.getenv("SECRET_KEY", "my_secret_key_12345")

FTP_HOST = os.getenv("FTP_HOST", "srv455240170.host.ultaserver.net")
FTP_USER = os.getenv("FTP_USER", "admin_admin")
FTP_PASS = os.getenv("FTP_PASS", "ApqK*.J6HPbQ2BM")
FTP_HLS_DIR = os.getenv("FTP_HLS_DIR", "/public_html/wp-content/uploads/secure-hls")  # Example: /public_html/wp-content/uploads/secure-hls

UPLOAD_DIR = "tmp_videos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# AES Functions
def pad(s):
    return s + (16 - len(s) % 16) * chr(16 - len(s) % 16)

def encrypt_url(url, key):
    key = sha256(key.encode()).digest()
    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ct_bytes = cipher.encrypt(pad(url).encode())
    return base64.b64encode(iv + ct_bytes).decode()

# Download with yt-dlp
def download_video(url):
    ydl_opts = {
        'outtmpl': f'{UPLOAD_DIR}/%(title).40s.%(ext)s',
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
        'merge_output_format': 'mp4'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'Untitled')
        height = info.get('height', 360)
        filename = ydl.prepare_filename(info).replace(".webm", ".mp4")
        return filename, title, height

# Convert to multi-res HLS
def convert_to_hls_multires(mp4_path, output_folder, max_height):
    os.makedirs(output_folder, exist_ok=True)
    streams = []
    filter_parts = []
    var_map_parts = []

    if max_height >= 1080:
        streams.append(("1920", "1080", "5000k"))
    if max_height >= 720:
        streams.append(("1280", "720", "2500k"))
    if max_height >= 360:
        streams.append(("640", "360", "1000k"))

    split_video = f"[0:v]split={len(streams)}" + ''.join(f"[v{i}]" for i in range(len(streams))) + ";"
    scale_filters = [f"[v{i}]scale=w={w}:h={h}[v{i}out]" for i, (w, h, _) in enumerate(streams)]
    audio_split = f"[0:a]asplit={len(streams)}" + ''.join(f"[a{i}]" for i in range(len(streams))) + ";"

    filter_complex = split_video + audio_split + ';'.join(scale_filters)

    cmd = [
        'ffmpeg', '-i', mp4_path,
        '-filter_complex', filter_complex
    ]

    for i, (_, _, bitrate) in enumerate(streams):
        cmd += [
            '-map', f'[v{i}out]', '-map', f'[a{i}]',
            f'-c:v:{i}', 'libx264', f'-b:v:{i}', bitrate,
            f'-c:a:{i}', 'aac', '-b:a', '128k'
        ]
        var_map_parts.append(f'v:{i},a:{i},name:{streams[i][1]}p')

    cmd += [
        '-f', 'hls',
        '-var_stream_map', ' '.join(var_map_parts),
        '-master_pl_name', 'master.m3u8',
        '-hls_time', '10',
        '-hls_list_size', '0',
        '-hls_segment_filename', f'{output_folder}/%v/segment_%03d.ts',
        f'{output_folder}/%v/playlist.m3u8'
    ]

    subprocess.run(cmd, check=True)
    return os.path.join(output_folder, 'master.m3u8')



# Upload to FTP

def upload_folder_to_ftp(local_folder, ftp_base_path):
    ftp = FTP(FTP_HOST)
    ftp.login(user=FTP_USER, passwd=FTP_PASS)
    folder_name = os.path.basename(local_folder)
    remote_path = f"{ftp_base_path}/{folder_name}"

    def upload_dir(path, remote):
        try:
            ftp.mkd(remote)
        except:
            pass
        ftp.cwd(remote)
        for item in os.listdir(path):
            local_item = os.path.join(path, item)
            if os.path.isdir(local_item):
                upload_dir(local_item, item)
                ftp.cwd("..")
            else:
                with open(local_item, 'rb') as f:
                    ftp.storbinary(f"STOR {item}", f)

    upload_dir(local_folder, remote_path)
    ftp.quit()
    return folder_name

# Upload to WP

def upload_to_wordpress(post_folder_name, title):
    session = requests.Session()
    session.auth = (WP_USER, WP_PASS)

    full_url = f"{WP_SITE}/wp-content/uploads/secure-hls/{post_folder_name}/master.m3u8"
    encrypted = encrypt_url(full_url, SECRET_KEY)
    stream_url = f"{WP_SITE}/stream.php?hls={quote(encrypted)}"

    content = f'''
<link rel=\"stylesheet\" href=\"https://cdn.plyr.io/3.7.8/plyr.css\" />
<video id=\"player\" playsinline controls>
  <source src=\"{stream_url}\" type=\"application/x-mpegURL\" />
</video>
<script src=\"https://cdn.plyr.io/3.7.8/plyr.polyfilled.js\"></script>
<script>
  document.addEventListener('DOMContentLoaded', () => {{
    new Plyr('#player');
  }});
</script>
'''

    post_data = {
        "title": title,
        "content": content,
        "status": "publish"
    }

    r = session.post(f"{WP_SITE}/wp-json/wp/v2/posts", json=post_data)
    if r.status_code in [200, 201]:
        print("✅ Post created:", r.json().get('link'))
    else:
        print("❌ Failed to create post:", r.text)

if __name__ == "__main__":
    while True:
        url = input("\n🎬 Enter video URL (or 'exit' to stop): ").strip()
        if url.lower() == 'exit':
            break

        mp4_path, title, max_height = download_video(url)
        print(f"⏳ Converting to HLS (max quality: {max_height}p)...")

        safe_title = ''.join(c if c.isalnum() else '_' for c in title)
        rand_suffix = ''.join(random.choices(string.digits, k=5))
        folder_name = f"{safe_title[:30]}_{rand_suffix}"
        hls_output = os.path.abspath(f"{UPLOAD_DIR}/{folder_name}")

        convert_to_hls_multires(mp4_path, hls_output, max_height)
        uploaded_folder = upload_folder_to_ftp(hls_output, FTP_HLS_DIR)
        upload_to_wordpress(uploaded_folder, title)

        os.remove(mp4_path)
        shutil.rmtree(hls_output)
        print("🧹 Cleaned up temporary files.")
